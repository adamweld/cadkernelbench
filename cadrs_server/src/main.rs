// SPDX-License-Identifier: MIT OR Apache-2.0

//! Line-oriented JSON server over cadrs_kernel, for the robustness benchmark. One request per
//! line on stdin, one reply per line on stdout, the same protocol as solidcore_server. It makes
//! kernel calls only; cases and scoring live in the Python side.
//!
//! Every reply is exactly one of:
//!   {"ok": {...}}     the request ran; kernel outcomes, including an empty boolean, are inside
//!   {"kerr": "..."}   cadrs_kernel returned an error for the kernel call that was asked for
//!   {"herr": "..."}   the request itself was wrong (bad handle, bad JSON, unknown op), or the
//!                     kernel broke its documented contract in a way the server cannot read: a
//!                     bug or a surprise to investigate, never to be counted against the kernel

use cadrs_kernel::native::CheckLevel;
use cadrs_kernel::{
    BodyId, BoolOp, DefaultKernel, EdgeId, Kernel, KernelError, PointClass, Primitive,
    Tessellation,
};
use nalgebra::{Isometry3, Matrix3, Point3, Rotation3, Translation3, UnitQuaternion, Vector3};
use serde_json::{Value, json};
use std::collections::HashMap;
use std::io::{BufRead, Write};

/// The band within which `classify` answers "on the boundary" (mm), as for OCCT's classifier.
const CLASSIFY_TOL: f64 = 1e-7;

/// Mesh chord: the same as the SMLib and solidcore runs, inside the benchmark's 0.01 mm band.
const CHORD: f64 = 3e-3;

/// A body held for the client, with its mesh once one is asked for.
struct Held {
    id: BodyId,
    mesh: Option<Mesh>,
}

struct Mesh {
    tris: Vec<[[f64; 3]; 3]>,
    defects: Value,
}

type Reply = Result<Value, Fail>;

enum Fail {
    Kernel(String),
    Harness(String),
}

fn kerr(e: &KernelError) -> Fail {
    match e {
        // An id the server holds that the kernel does not know is the server's mistake.
        KernelError::UnknownBody(_) => Fail::Harness(format!("{e:?}")),
        _ => Fail::Kernel(format!("{e:?}")),
    }
}

fn herr(s: &str) -> Fail {
    Fail::Harness(s.to_owned())
}

fn num(v: &Value) -> Result<f64, Fail> {
    v.as_f64().ok_or_else(|| herr("expected a number"))
}

fn v3(v: &Value) -> Result<[f64; 3], Fail> {
    Ok([num(&v[0])?, num(&v[1])?, num(&v[2])?])
}

fn handle_of(req: &Value, key: &str) -> Result<u64, Fail> {
    req[key].as_u64().ok_or_else(|| herr("missing handle"))
}

fn dims(req: &Value, n: usize) -> Result<Vec<f64>, Fail> {
    let d: Vec<f64> = req["dims"]
        .as_array()
        .ok_or_else(|| herr("missing dims"))?
        .iter()
        .map(num)
        .collect::<Result<_, _>>()?;
    if d.len() != n {
        return Err(herr("wrong number of dims"));
    }
    Ok(d)
}

struct Server {
    k: DefaultKernel,
    held: HashMap<u64, Held>,
    next: u64,
}

impl Server {
    fn id(&self, req: &Value, key: &str) -> Result<BodyId, Fail> {
        let h = handle_of(req, key)?;
        self.held.get(&h).map(|x| x.id).ok_or_else(|| herr("bad handle"))
    }

    fn store(&mut self, id: BodyId) -> u64 {
        self.next += 1;
        self.held.insert(self.next, Held { id, mesh: None });
        self.next
    }

    /// The one body a result must hold ([`Kernel::boolean`] and the others give one).
    fn one(&mut self, bodies: &[BodyId]) -> Result<BodyId, Fail> {
        match bodies {
            [b] => Ok(*b),
            _ => {
                for b in bodies {
                    self.k.release(*b);
                }
                Err(herr("the kernel returned other than one body"))
            }
        }
    }

    /// Whether the body is a closed manifold solid: it has a solid, every shell closed, no
    /// sheets, wires or loose points, and every edge of a face that is not degenerate used by
    /// exactly two coedges of the faces, once each way.
    fn manifold(&self, id: BodyId) -> Result<bool, Fail> {
        let b = self.k.get(id).map_err(|e| kerr(&e))?;
        if !b.is_solid() || !b.wires().is_empty() || !b.points().is_empty() {
            return Ok(false);
        }
        if b.shells().iter().any(|s| !s.closed) {
            return Ok(false);
        }
        let mut uses = vec![(0usize, 0usize); b.edges().len()];
        for f in b.faces() {
            for l in &f.loops {
                for c in l {
                    let u = uses.get_mut(c.edge).ok_or_else(|| herr("coedge names no edge"))?;
                    if c.fwd { u.0 += 1 } else { u.1 += 1 }
                }
            }
        }
        // An edge no face uses (a leftover entry in the edge list, in no wire) bounds nothing
        // and is not part of the boundary: it is passed over.
        Ok(b.edges().iter().zip(&uses).all(|(e, &(f, r))| e.degenerate || (f == 0 && r == 0) || (f == 1 && r == 1)))
    }

    /// Validity as two separate verdicts: the kernel's own check at its full level, and whether
    /// the body is a closed manifold solid.
    fn validity(&self, id: BodyId) -> Result<Value, Fail> {
        let problems = self.k.get(id).map_err(|e| kerr(&e))?.check_with(CheckLevel::Full);
        let solid = self.manifold(id)?;
        let first: Vec<&String> = problems.iter().take(3).collect();
        Ok(json!({"solid": solid, "solid_err": null, "check": problems.is_empty(),
                  "check_err": null, "check_tests": first, "n_problems": problems.len()}))
    }

    fn volume_json(&self, id: BodyId) -> Value {
        match self.k.mass_properties(id) {
            Ok(m) if m.volume.is_finite() => json!({"vol": m.volume}),
            Ok(_) => json!({"vol_err": "not finite"}),
            Err(e) => json!({"vol_err": format!("{e:?}")}),
        }
    }

    fn mesh_of(&self, id: BodyId) -> Result<Mesh, Fail> {
        let q = Tessellation { deflection: CHORD, ..Tessellation::default() };
        let m = self.k.tessellate(id, q).map_err(|e| kerr(&e))?;
        let p = |i: u32| m.positions.get(i as usize).map(|v| [v.x, v.y, v.z]);
        let mut tris = Vec::with_capacity(m.indices.len());
        for t in &m.indices {
            match (p(t[0]), p(t[1]), p(t[2])) {
                (Some(a), Some(b), Some(c)) => tris.push([a, b, c]),
                _ => return Err(Fail::Kernel("mesh: triangle index out of range".to_owned())),
            }
        }
        // The mesh's own enclosed volume against the exact one: a mesh with a hole or a flipped
        // patch shows here, and its winding numbers would not be trusted.
        let mut v6 = 0.0;
        for [a, b, c] in &tris {
            v6 += a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0])
                + a[2] * (b[0] * c[1] - b[1] * c[0]);
        }
        let exact = self.k.mass_properties(id).map(|m| m.volume).unwrap_or(f64::NAN);
        let rel = ((v6 / 6.0) - exact).abs() / exact.abs().max(1e-12);
        let defects = json!({"triangles": tris.len(), "volume_rel_diff": rel,
                             "volume_off": !(rel < 1e-3)});
        Ok(Mesh { tris, defects })
    }

    fn handle(&mut self, req: &Value) -> Reply {
        match req["op"].as_str().unwrap_or("") {
            "make" => {
                // The primitive in its local frame (axis +z, seam toward +x), then placed by the
                // rigid motion whose matrix rows 0-2 are the images of x, y, z and row 3 the
                // translation (p' = p·A + t), as for solidcore_server.
                let p = v3(&req["p"])?;
                let o = Point3::new(p[0], p[1], p[2]);
                let z = Vector3::z_axis();
                let prim = match req["kind"].as_str().unwrap_or("") {
                    "box" => {
                        let d = dims(req, 3)?;
                        Primitive::Box { min: o, max: Point3::new(p[0] + d[0], p[1] + d[1], p[2] + d[2]) }
                    }
                    "cyl" => {
                        let d = dims(req, 2)?;
                        Primitive::Cylinder { base: o, axis: z, radius: d[0], height: d[1] }
                    }
                    "sph" => {
                        let d = dims(req, 1)?;
                        Primitive::Sphere { center: o, radius: d[0], axis: z, seam: Vector3::x_axis() }
                    }
                    "cone" => {
                        let d = dims(req, 3)?;
                        Primitive::Cone { base: o, axis: z, base_radius: d[0], top_radius: d[1], height: d[2] }
                    }
                    "torus" => {
                        let d = dims(req, 2)?;
                        Primitive::Torus { center: o, axis: z, major: d[0], minor: d[1] }
                    }
                    _ => return Err(herr("unknown kind")),
                };
                let mut m = [[0.0f64; 4]; 4];
                for (i, row) in m.iter_mut().enumerate() {
                    for (j, x) in row.iter_mut().enumerate() {
                        *x = num(&req["m"][i][j])?;
                    }
                }
                // Column j of the rotation is the image of local axis j: row j of the matrix.
                let r = Matrix3::new(
                    m[0][0], m[1][0], m[2][0], m[0][1], m[1][1], m[2][1], m[0][2], m[1][2], m[2][2],
                );
                let rot = UnitQuaternion::from_rotation_matrix(&Rotation3::from_matrix_unchecked(r));
                let motion = Isometry3::from_parts(Translation3::new(m[3][0], m[3][1], m[3][2]), rot);
                let made = self.k.primitive(&prim).map_err(|e| kerr(&e))?;
                let local = self.one(&made.bodies)?;
                let placed = self.k.transform(local, &motion);
                self.k.release(local);
                let placed = placed.map_err(|e| kerr(&e))?;
                let id = self.one(&placed.bodies)?;
                Ok(json!({"h": self.store(id)}))
            }
            "bool" => {
                let (a, b) = (self.id(req, "a")?, self.id(req, "b")?);
                let op = match req["kind"].as_str().unwrap_or("") {
                    "fuse" => BoolOp::Union,
                    "cut" => BoolOp::Subtract,
                    "common" => BoolOp::Intersect,
                    _ => return Err(herr("unknown op")),
                };
                // Operations leave their inputs as they were: no copies needed.
                match self.k.boolean(op, a, &[b]) {
                    // The kernel's way of saying the result is empty: an answer, judged by the
                    // point test like any other.
                    Err(KernelError::EmptyResult(_)) => Ok(json!({"empty": true})),
                    Err(e) => Err(kerr(&e)),
                    Ok(r) => {
                        let id = self.one(&r.bodies)?;
                        let mut out = self.volume_json(id);
                        out["valid"] = self.validity(id)?;
                        out["h"] = json!(self.store(id));
                        Ok(out)
                    }
                }
            }
            "valid" => {
                let id = self.id(req, "h")?;
                self.validity(id)
            }
            "check_text" => {
                let id = self.id(req, "h")?;
                let p = self.k.get(id).map_err(|e| kerr(&e))?.check_with(CheckLevel::Full);
                Ok(json!({"text": p.join("\n")}))
            }
            "manifold_diag" => {
                // Why the manifold test failed: the body's counts and each edge used other than
                // once each way. For reading a failure, not used by the benchmark's runs.
                let id = self.id(req, "h")?;
                let b = self.k.get(id).map_err(|e| kerr(&e))?;
                let mut uses = vec![(0usize, 0usize, 0usize); b.edges().len()];
                for (fi, f) in b.faces().iter().enumerate() {
                    for l in &f.loops {
                        for c in l {
                            if let Some(u) = uses.get_mut(c.edge) {
                                if c.fwd { u.0 += 1 } else { u.1 += 1 }
                                u.2 = fi;
                            }
                        }
                    }
                }
                let bad: Vec<Value> = b.edges().iter().zip(&uses).enumerate()
                    .filter(|(_, (e, u))| !e.degenerate && !(u.0 == 1 && u.1 == 1) && !(u.0 == 0 && u.1 == 0))
                    .map(|(i, (e, u))| json!({"edge": i, "fwd": u.0, "rev": u.1, "closed": e.closed(),
                        "a": [e.point(e.t[0]).x, e.point(e.t[0]).y, e.point(e.t[0]).z]}))
                    .collect();
                Ok(json!({"solids": b.solids().len(), "shells": b.shells().len(),
                          "open_shells": b.shells().iter().filter(|s| !s.closed).count(),
                          "wires": b.wires().len(), "points": b.points().len(),
                          "faces": b.faces().len(), "edges": b.edges().len(), "bad_edges": bad}))
            }
            "vol" => {
                let id = self.id(req, "h")?;
                Ok(self.volume_json(id))
            }
            "bbox" => {
                let id = self.id(req, "h")?;
                let b = self.k.bounding_box(id).map_err(|e| kerr(&e))?;
                Ok(json!({"lo": [b.min.x, b.min.y, b.min.z], "hi": [b.max.x, b.max.y, b.max.z]}))
            }
            "classify" => {
                let id = self.id(req, "h")?;
                let pts = req["pts"].as_array().ok_or_else(|| herr("missing pts"))?;
                let mut cls = Vec::with_capacity(pts.len());
                let mut errs = Vec::new();
                for p in pts {
                    let q = v3(p)?;
                    cls.push(match self.k.classify(id, Point3::new(q[0], q[1], q[2]), CLASSIFY_TOL) {
                        Ok(PointClass::Inside) => 1,
                        Ok(PointClass::Outside) => 0,
                        Ok(PointClass::OnBoundary) => -1,
                        Err(e) => {
                            errs.push(format!("{e:?}"));
                            -2
                        }
                    });
                }
                Ok(json!({"cls": cls, "errs": errs}))
            }
            "wn" => {
                // Winding numbers of points about the body's mesh; the mesh is made once per body.
                let h = handle_of(req, "h")?;
                let id = self.held.get(&h).map(|x| x.id).ok_or_else(|| herr("bad handle"))?;
                if self.held.get(&h).is_some_and(|x| x.mesh.is_none()) {
                    let m = self.mesh_of(id)?;
                    if let Some(x) = self.held.get_mut(&h) {
                        x.mesh = Some(m);
                    }
                }
                let mesh = self.held.get(&h).and_then(|x| x.mesh.as_ref()).ok_or_else(|| herr("no mesh"))?;
                let pts = req["pts"].as_array().ok_or_else(|| herr("missing pts"))?;
                let w: Vec<f64> = pts.iter().map(|p| v3(p).map(|q| winding(&mesh.tris, q))).collect::<Result<_, _>>()?;
                Ok(json!({"w": w, "defects": mesh.defects}))
            }
            "edges" => {
                // Every edge between two different faces, with the angle between the faces'
                // outward normals at 10%, 50% and 90% of its parameter range, as for OCCT, and
                // its length. An edge whose normals the kernel refuses is reported and not
                // offered.
                let id = self.id(req, "h")?;
                let infos = self.k.edges(id).map_err(|e| kerr(&e))?;
                let body = self.k.get(id).map_err(|e| kerr(&e))?.clone();
                let mut out = Vec::new();
                let mut refused = Vec::new();
                for e in infos {
                    let (Some(f0), Some(f1)) = (e.faces[0], e.faces[1]) else { continue };
                    if f0 == f1 {
                        continue; // a seam
                    }
                    let Some(edge) = body.edges().get(e.id.0 as usize) else {
                        return Err(herr("edge id is not an index of the body's edges"));
                    };
                    if edge.degenerate {
                        continue;
                    }
                    let pts: Vec<Point3<f64>> = [0.1, 0.5, 0.9]
                        .iter()
                        .map(|f| edge.point(edge.t[0] + f * (edge.t[1] - edge.t[0])))
                        .collect();
                    let n = (self.k.face_normals_at(id, f0, &pts), self.k.face_normals_at(id, f1, &pts));
                    let (n0, n1) = match n {
                        (Ok(a), Ok(b)) if a.len() == 3 && b.len() == 3 => (a, b),
                        (Err(x), _) | (_, Err(x)) => {
                            refused.push(format!("normal {x:?}"));
                            continue;
                        }
                        _ => return Err(herr("face_normals_at gave the wrong number of normals")),
                    };
                    let ang: Vec<f64> = n0.iter().zip(&n1).map(|(a, b)| a.dot(b).clamp(-1.0, 1.0).acos().to_degrees()).collect();
                    out.push(json!({"i": e.id.0, "len": e.length, "angs": ang}));
                }
                Ok(json!({"edges": out, "refused": refused}))
            }
            "fillet" => {
                // A constant-radius rolling-ball round on the given edges: Kernel::fillet.
                let id = self.id(req, "h")?;
                let edges: Vec<EdgeId> = req["edges"]
                    .as_array()
                    .ok_or_else(|| herr("missing edges"))?
                    .iter()
                    .map(|e| e.as_u64().map(EdgeId).ok_or_else(|| herr("bad edge")))
                    .collect::<Result<_, _>>()?;
                let r = num(&req["r"])?;
                let res = self.k.fillet(id, &edges, r).map_err(|e| kerr(&e))?;
                let f = self.one(&res.bodies)?;
                let v = self.validity(f);
                self.k.release(f);
                v
            }
            "fillet_probe" => {
                // For checking that a fillet changed the body: the volume and face count before
                // and after Kernel::fillet. Not used by the benchmark's runs.
                let id = self.id(req, "h")?;
                let edges: Vec<EdgeId> = req["edges"]
                    .as_array()
                    .ok_or_else(|| herr("missing edges"))?
                    .iter()
                    .map(|e| e.as_u64().map(EdgeId).ok_or_else(|| herr("bad edge")))
                    .collect::<Result<_, _>>()?;
                let r = num(&req["r"])?;
                let before = (self.k.mass_properties(id).map_err(|e| kerr(&e))?.volume, self.k.face_count(id).map_err(|e| kerr(&e))?);
                let res = self.k.fillet(id, &edges, r).map_err(|e| kerr(&e))?;
                let f = self.one(&res.bodies)?;
                let after = (self.k.mass_properties(f).map(|m| m.volume), self.k.face_count(f));
                let (va, fa) = (after.0.map_err(|e| kerr(&e))?, after.1.map_err(|e| kerr(&e))?);
                let ends: Vec<Value> = self.k.edges(id).map_err(|e| kerr(&e))?.iter()
                    .filter(|e| edges.contains(&e.id))
                    .map(|e| json!([[e.start.x, e.start.y, e.start.z], [e.mid.x, e.mid.y, e.mid.z], [e.end.x, e.end.y, e.end.z]]))
                    .collect();
                Ok(json!({"vol_before": before.0, "faces_before": before.1, "vol_after": va,
                          "faces_after": fa, "h": self.store(f), "edge_points": ends}))
            }
            "free" => {
                for h in req["hs"].as_array().ok_or_else(|| herr("missing hs"))? {
                    if let Some(x) = self.held.remove(&h.as_u64().unwrap_or(0)) {
                        self.k.release(x.id);
                    }
                }
                Ok(json!({}))
            }
            _ => Err(herr("unknown request")),
        }
    }
}

/// Generalised winding number of the mesh about `q` (van Oosterom and Strackee's solid angle).
fn winding(tris: &[[[f64; 3]; 3]], q: [f64; 3]) -> f64 {
    let mut total = 0.0;
    for t in tris {
        let a = [t[0][0] - q[0], t[0][1] - q[1], t[0][2] - q[2]];
        let b = [t[1][0] - q[0], t[1][1] - q[1], t[1][2] - q[2]];
        let c = [t[2][0] - q[0], t[2][1] - q[1], t[2][2] - q[2]];
        let dot = |u: [f64; 3], v: [f64; 3]| u[0] * v[0] + u[1] * v[1] + u[2] * v[2];
        let (la, lb, lc) = (dot(a, a).sqrt(), dot(b, b).sqrt(), dot(c, c).sqrt());
        let bxc = [b[1] * c[2] - b[2] * c[1], b[2] * c[0] - b[0] * c[2], b[0] * c[1] - b[1] * c[0]];
        let num = dot(a, bxc);
        let den = la * lb * lc + dot(a, b) * lc + dot(b, c) * la + dot(c, a) * lb;
        total += num.atan2(den);
    }
    total / (2.0 * std::f64::consts::PI)
}

/// Exits when the process that started this one is gone, so a worker killed for a stall does
/// not leave its server computing.
fn watch_parent() {
    let parent = std::os::unix::process::parent_id();
    std::thread::spawn(move || {
        loop {
            std::thread::sleep(std::time::Duration::from_millis(500));
            if std::os::unix::process::parent_id() != parent {
                std::process::exit(0);
            }
        }
    });
}

fn main() {
    watch_parent();
    let mut s = Server { k: DefaultKernel::new(), held: HashMap::new(), next: 0 };
    let stdin = std::io::stdin();
    let mut out = std::io::stdout().lock();
    for line in stdin.lock().lines() {
        let Ok(line) = line else { break };
        let reply = match serde_json::from_str::<Value>(&line) {
            Ok(req) => match s.handle(&req) {
                Ok(v) => json!({"ok": v}),
                Err(Fail::Kernel(e)) => json!({"kerr": e}),
                Err(Fail::Harness(e)) => json!({"herr": e}),
            },
            Err(e) => json!({"herr": format!("bad json: {e}")}),
        };
        if writeln!(out, "{reply}").is_err() || out.flush().is_err() {
            break;
        }
    }
}
