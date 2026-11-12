// SPDX-License-Identifier: MIT OR Apache-2.0

//! Line-oriented JSON server over solidcore-ops, for the robustness
//! benchmark. One request per line on stdin, one reply per line on stdout.
//! It makes kernel calls only; cases and scoring live in the Python side.
//!
//! Every reply is exactly one of:
//!   {"ok": {...}}     the request ran; kernel outcomes, including refusals that are part of
//!                     a normal answer (an empty boolean), are inside
//!   {"kerr": "..."}   solidcore returned an error for the kernel call that was asked for
//!   {"herr": "..."}   the request itself was wrong (bad handle, bad JSON, unknown op): a bug
//!                     in the benchmark, never to be counted against the kernel
//! The two error kinds are kept apart so the Python side can stop on a harness error.

use serde_json::{json, Value};
use solidcore_ops::{
    blend_ordered, edge_faces_along_ordered, make_box, make_cone, make_cylinder, make_sphere,
    make_torus, Blend, Body, BooleanOp, CheckLevel, Corners, Error, Order, PointClass, Turn,
};
use std::collections::HashMap;
use std::io::{BufRead, Write};

/// A body held for the client, with the record order its edge indices refer to, once asked.
struct Held {
    body: Body,
    order: Option<Order>,
    mesh: Option<Mesh>,
}

/// A body's tessellation by solidcore's own mesher, for classifying points by winding number,
/// with what the mesher reported it could not do to tolerance.
struct Mesh {
    tris: Vec<[[f64; 3]; 3]>,
    defects: Value,
}

/// Mesh chord: the same as the SMLib run, inside the benchmark's 0.01 mm band.
const CHORD: f64 = 3e-3;

fn mesh_of(b: &Body) -> Result<Mesh, Fail> {
    let (record, _) = b.to_record().map_err(|e| kerr(&e))?;
    let (lo, hi) = b.bounds().map_err(|e| kerr(&e))?;
    let size = ((hi[0] - lo[0]).powi(2) + (hi[1] - lo[1]).powi(2) + (hi[2] - lo[2]).powi(2)).sqrt();
    let (plan, stats) = solidcore_tess::plan(&record, &solidcore_tess::MeshTolerance::chord(CHORD), size)
        .map_err(|e| Fail::Kernel(format!("mesh plan: {e}")))?;
    let (mesh, refused) = plan.evaluate();
    let p = |i: u32| mesh.positions.get(i as usize).map(|v| [v.x, v.y, v.z]);
    let mut tris = Vec::with_capacity(mesh.triangles.len());
    for t in &mesh.triangles {
        match (p(t[0]), p(t[1]), p(t[2])) {
            (Some(a), Some(b), Some(c)) => tris.push([a, b, c]),
            _ => return Err(Fail::Kernel("mesh: triangle index out of range".to_owned())),
        }
    }
    let defects = json!({
        "lenient": stats.lenient.len(), "unmeshed": stats.unmeshed.len(),
        "over_tolerance": stats.over_tolerance.len(), "edges_capped": stats.edges_capped.len(),
        "unsampled_edges": stats.unsampled_edges.len(), "refused_at_evaluate": refused.len(),
        "triangles": tris.len()});
    Ok(Mesh { tris, defects })
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

type Reply = Result<Value, Fail>;

enum Fail {
    Kernel(String),
    Harness(String),
}

fn kerr(e: &Error) -> Fail {
    Fail::Kernel(format!("{e:?}"))
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

fn get<'a>(bodies: &'a HashMap<u64, Held>, h: u64) -> Result<&'a Held, Fail> {
    bodies.get(&h).ok_or_else(|| herr("bad handle"))
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

/// Validity as two separate verdicts: the kernel's own check, and whether the body is a closed
/// manifold solid. Either one that could not run is reported with its error, not as a verdict.
fn validity(b: &Body) -> Value {
    let (solid, solid_err) = match b.is_manifold_solid() {
        Ok(v) => (Some(v), None),
        Err(e) => (None, Some(format!("{e:?}"))),
    };
    let (check, check_err, check_tests) = match b.check(CheckLevel::Geometry) {
        Ok(r) => (Some(r.is_valid()), None, r.failed_tests()),
        Err(e) => (None, Some(format!("{e:?}")), vec![]),
    };
    json!({"solid": solid, "solid_err": solid_err, "check": check,
           "check_err": check_err, "check_tests": check_tests})
}

fn volume_json(b: &Body) -> Value {
    match b.volume(1e-6) {
        Ok(v) if v.is_finite() => json!({"vol": v}),
        Ok(_) => json!({"vol_err": "not finite"}),
        Err(e) => json!({"vol_err": format!("{e:?}")}),
    }
}

fn store(bodies: &mut HashMap<u64, Held>, next: &mut u64, body: Body) -> u64 {
    *next += 1;
    bodies.insert(*next, Held { body, order: None, mesh: None });
    *next
}

fn handle(req: &Value, bodies: &mut HashMap<u64, Held>, next: &mut u64) -> Reply {
    match req["op"].as_str().unwrap_or("") {
        "make" => {
            let p = v3(&req["p"])?;
            let made = match req["kind"].as_str().unwrap_or("") {
                "box" => {
                    let d = dims(req, 3)?;
                    make_box(p, [d[0], d[1], d[2]])
                }
                "cyl" => {
                    let d = dims(req, 2)?;
                    make_cylinder(p, d[0], d[1])
                }
                "sph" => {
                    let d = dims(req, 1)?;
                    make_sphere(p, d[0])
                }
                "cone" => {
                    let d = dims(req, 3)?;
                    make_cone(p, d[0], d[1], d[2])
                }
                "torus" => {
                    let d = dims(req, 2)?;
                    make_torus(p, d[0], d[1])
                }
                _ => return Err(herr("unknown kind")),
            };
            let body = made.map_err(|e| kerr(&e))?;
            let mut m = [[0.0f64; 4]; 4];
            for (i, row) in m.iter_mut().enumerate() {
                for (j, x) in row.iter_mut().enumerate() {
                    *x = num(&req["m"][i][j])?;
                }
            }
            body.transform(&m).map_err(|e| kerr(&e))?;
            Ok(json!({"h": store(bodies, next, body)}))
        }
        "bool" => {
            let a = &get(bodies, handle_of(req, "a")?)?.body;
            let b = &get(bodies, handle_of(req, "b")?)?.body;
            let kind = match req["kind"].as_str().unwrap_or("") {
                "fuse" => BooleanOp::Union,
                "cut" => BooleanOp::Subtract,
                "common" => BooleanOp::Intersect,
                _ => return Err(herr("unknown op")),
            };
            // The operation consumes its operands; the inputs must stay usable, so it is given
            // copies. With "consume", for checking that copying changes nothing, the operands
            // themselves are given and their handles are dropped.
            let (ca, cb) = if req["consume"].as_bool() == Some(true) {
                let (ha, hb) = (handle_of(req, "a")?, handle_of(req, "b")?);
                let ca = bodies.remove(&ha).ok_or_else(|| herr("bad handle"))?.body;
                let cb = bodies.remove(&hb).ok_or_else(|| herr("bad handle"))?.body;
                (ca, cb)
            } else {
                (a.copy().map_err(|e| kerr(&e))?, b.copy().map_err(|e| kerr(&e))?)
            };
            match solidcore_ops::boolean::boolean(ca, cb, kind) {
                Ok(None) => Ok(json!({"empty": true})),
                Ok(Some(r)) => {
                    let mut out = volume_json(&r);
                    out["valid"] = validity(&r);
                    out["h"] = json!(store(bodies, next, r));
                    Ok(out)
                }
                Err(e) => Err(kerr(&e)),
            }
        }
        "valid" => Ok(validity(&get(bodies, handle_of(req, "h")?)?.body)),
        "check_text" => {
            // The kernel's full check report, for reading why a body failed it.
            let b = &get(bodies, handle_of(req, "h")?)?.body;
            let r = b.check(CheckLevel::Geometry).map_err(|e| kerr(&e))?;
            Ok(json!({"text": r.text}))
        }
        "vol" => Ok(volume_json(&get(bodies, handle_of(req, "h")?)?.body)),
        "bbox" => {
            let b = &get(bodies, handle_of(req, "h")?)?.body;
            let (lo, hi) = b.bounds().map_err(|e| kerr(&e))?;
            Ok(json!({"lo": lo, "hi": hi}))
        }
        "classify" => {
            let b = &get(bodies, handle_of(req, "h")?)?.body;
            let pts = req["pts"].as_array().ok_or_else(|| herr("missing pts"))?;
            let mut cls = Vec::with_capacity(pts.len());
            let mut errs = Vec::new();
            for p in pts {
                cls.push(match b.classify_point(v3(p)?) {
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
            let held = bodies.get_mut(&h).ok_or_else(|| herr("bad handle"))?;
            if held.mesh.is_none() {
                held.mesh = Some(mesh_of(&held.body)?);
            }
            let mesh = held.mesh.as_ref().ok_or_else(|| herr("no mesh"))?;
            let pts = req["pts"].as_array().ok_or_else(|| herr("missing pts"))?;
            let w: Vec<f64> = pts.iter().map(|p| v3(p).map(|q| winding(&mesh.tris, q))).collect::<Result<_, _>>()?;
            Ok(json!({"w": w, "defects": mesh.defects}))
        }
        "edges" => {
            // Every record edge between two different faces, with the angle between the two
            // faces' outward normals at the middle of the edge and its length. ops gives the
            // normals at the edge's middle only. An edge whose faces or normals the kernel
            // refuses (a pole, an apex, a seam) is reported with the refusal and is not offered.
            let h = handle_of(req, "h")?;
            let held = bodies.get_mut(&h).ok_or_else(|| herr("bad handle"))?;
            let (_, order) = held.body.to_record().map_err(|e| kerr(&e))?;
            let b = &held.body;
            let mut out = Vec::new();
            let mut refused = Vec::new();
            for i in 0..order.edges.len() {
                let faces = match edge_faces_along_ordered(b, &order, i, [1.0, 0.0, 0.0]) {
                    Ok(f) => f,
                    Err(e) => {
                        refused.push(format!("faces {e:?}"));
                        continue;
                    }
                };
                let (f0, f1) = (faces[0].0, faces[1].0);
                if f0 == f1 {
                    continue; // a seam
                }
                let n = (b.face_normal_at_edge(&order, i, f0), b.face_normal_at_edge(&order, i, f1));
                let (n0, n1) = match n {
                    (Ok(a), Ok(c)) => (a.value, c.value),
                    (Err(e), _) | (_, Err(e)) => {
                        refused.push(format!("normal {e:?}"));
                        continue;
                    }
                };
                let len = match b.edge_length(&order, i, 1e-6) {
                    Ok(l) => l,
                    Err(e) => {
                        refused.push(format!("length {e:?}"));
                        continue;
                    }
                };
                let dot = (n0[0] * n1[0] + n0[1] * n1[1] + n0[2] * n1[2]).clamp(-1.0, 1.0);
                out.push(json!({"i": i, "len": len, "ang": dot.acos().to_degrees()}));
            }
            held.order = Some(order);
            Ok(json!({"edges": out, "refused": refused}))
        }
        "fillet" => {
            // A constant-radius rolling-ball round on the given record edges, corners filled
            // as the kernel builds them: blend() with its defaults, on a copy.
            let held = get(bodies, handle_of(req, "h")?)?;
            let order = held.order.as_ref().ok_or_else(|| herr("edges not listed first"))?;
            let edges: Vec<usize> = req["edges"]
                .as_array()
                .ok_or_else(|| herr("missing edges"))?
                .iter()
                .map(|e| e.as_u64().map(|x| x as usize).ok_or_else(|| herr("bad edge")))
                .collect::<Result<_, _>>()?;
            let r = num(&req["r"])?;
            let (copy, corder) = held.body.copy_with_order(order).map_err(|e| kerr(&e))?;
            blend_ordered(&copy, &corder, Blend::Round, &edges, &[r], &[], Corners::Filled, Turn::Mitre)
                .map_err(|e| kerr(&e))?;
            Ok(validity(&copy))
        }
        "free" => {
            for h in req["hs"].as_array().ok_or_else(|| herr("missing hs"))? {
                bodies.remove(&h.as_u64().unwrap_or(0));
            }
            Ok(json!({}))
        }
        _ => Err(herr("unknown request")),
    }
}

/// Exits when the process that started this one is gone, so a worker killed for a stall does
/// not leave its server computing.
fn watch_parent() {
    let parent = std::os::unix::process::parent_id();
    std::thread::spawn(move || loop {
        std::thread::sleep(std::time::Duration::from_millis(500));
        if std::os::unix::process::parent_id() != parent {
            std::process::exit(0);
        }
    });
}

fn main() {
    watch_parent();
    let mut bodies: HashMap<u64, Held> = HashMap::new();
    let mut next = 0u64;
    let stdin = std::io::stdin();
    let mut out = std::io::stdout().lock();
    for line in stdin.lock().lines() {
        let Ok(line) = line else { break };
        let reply = match serde_json::from_str::<Value>(&line) {
            Ok(req) => match handle(&req, &mut bodies, &mut next) {
                Ok(v) => json!({"ok": v}),
                Err(Fail::Kernel(s)) => json!({"kerr": s}),
                Err(Fail::Harness(s)) => json!({"herr": s}),
            },
            Err(e) => json!({"herr": format!("bad json: {e}")}),
        };
        if writeln!(out, "{reply}").is_err() || out.flush().is_err() {
            break;
        }
    }
}
