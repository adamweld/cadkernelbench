// SPDX-License-Identifier: MIT OR Apache-2.0

//! One model, one process: the corpus operations on a STEP file, in cadrs's kernel.
//!
//!     cadrs-corpus MODEL.step
//!
//! The same operations, sizes and choices as corpus/occt_worker.py (see corpus/ops.py and
//! corpus/README.md), reported the same way: a JSON line as each operation starts and one as it
//! ends. A panic ends the process, which the driver records as a crash in the operation that had
//! started. Nothing of the model's geometry is printed.

use cadrs_kernel::native::CheckLevel;
use cadrs_kernel::{BodyId, BoolOp, DefaultKernel, EdgeId, Kernel, Primitive, SurfaceKind, Tessellation};
use nalgebra::{Point3, Vector3};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::time::Instant;

const FILLETS: usize = 3;

fn emit(v: Value) {
    println!("{v}");
}

/// Runs one operation and reports it; Ok(None) where the kernel declined.
fn op<T>(name: &str, extra: Value, f: impl FnOnce() -> Result<T, String>, describe: impl FnOnce(&T) -> Value) -> Option<T> {
    let mut start = json!({"start": name});
    merge(&mut start, &extra);
    emit(start);
    let t = Instant::now();
    let r = f();
    let s = (t.elapsed().as_secs_f64() * 1e4).round() / 1e4;
    let mut out = match &r {
        Ok(v) => {
            let mut o = json!({"op": name, "status": "ok", "s": s});
            merge(&mut o, &describe(v));
            o
        }
        Err(e) => json!({"op": name, "status": "error", "reason": e.chars().take(300).collect::<String>(), "s": s}),
    };
    merge(&mut out, &extra);
    emit(out);
    r.ok()
}

fn merge(a: &mut Value, b: &Value) {
    if let (Some(a), Some(b)) = (a.as_object_mut(), b.as_object()) {
        for (k, v) in b {
            a.insert(k.clone(), v.clone());
        }
    }
}

fn e<E: std::fmt::Debug>(x: E) -> String {
    format!("{x:?}")
}

/// k distinct indices below n, from the file name, as ops.pick does: Python's random.sample is not
/// reproduced, so the choice differs from OCCT's; both are fixed per model.
fn pick(n: usize, k: usize, path: &str) -> Vec<usize> {
    let name = std::path::Path::new(path).file_name().map(|s| s.to_string_lossy().to_string()).unwrap_or_default();
    let h = Sha256::digest(name.as_bytes());
    let mut state = u64::from_be_bytes(h[..8].try_into().unwrap());
    let mut idx: Vec<usize> = (0..n).collect();
    let k = k.min(n);
    for i in 0..k {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        let j = i + (state as usize) % (n - i);
        idx.swap(i, j);
    }
    let mut out = idx[..k].to_vec();
    out.sort();
    out
}

fn valid(k: &DefaultKernel, id: BodyId) -> Result<bool, String> {
    Ok(k.get(id).map_err(e)?.check_with(CheckLevel::Full).is_empty())
}

fn main() {
    let path = std::env::args().nth(1).expect("usage: cadrs-corpus MODEL.step");
    let mut k = DefaultKernel::new();
    let bytes = std::fs::read(&path).expect("read the model");
    let Some((bodies, _)) = op("import", json!({}), || {
        let b = k.import_step(&bytes).map_err(e)?;
        let (mut solids, mut shells, mut faces, mut edges) = (0, 0, 0, 0);
        for id in &b {
            let body = k.get(*id).map_err(e)?;
            solids += body.solids().len();
            shells += body.shells().len();
            faces += body.faces().len();
            edges += body.edges().len();
        }
        let n = b.len();
        Ok((b, json!({"bodies": n, "solids": solids, "shells": shells, "faces": faces, "edges": edges})))
    }, |r: &(Vec<BodyId>, Value)| r.1.clone()) else { return };

    op("valid", json!({}), || bodies.iter().try_fold(true, |a, id| Ok(a & valid(&k, *id)?)), |v| json!({"valid": v}));
    let masses: Vec<Option<f64>> = bodies.iter().map(|id| k.mass_properties(*id).ok().map(|m| m.volume)).collect();
    op("mass", json!({}), || {
        let (mut v, mut a) = (0.0, 0.0);
        for id in &bodies {
            let m = k.mass_properties(*id).map_err(e)?;
            v += m.volume;
            a += m.surface_area;
        }
        Ok((v, a))
    }, |m| json!({"volume": m.0, "area": m.1}));
    op("kinds", json!({}), || {
        let mut c = serde_json::Map::new();
        for id in &bodies {
            for f in k.faces(*id).map_err(e)? {
                let name = match f.kind {
                    SurfaceKind::Plane => "plane", SurfaceKind::Cylinder => "cylinder", SurfaceKind::Cone => "cone",
                    SurfaceKind::Sphere => "sphere", SurfaceKind::Torus => "torus", _ => "other",
                };
                let n = c.get(name).and_then(|v| v.as_u64()).unwrap_or(0);
                c.insert(name.into(), json!(n + 1));
            }
        }
        Ok(Value::Object(c))
    }, |c| json!({"kinds": c}));
    op("roundtrip", json!({}), || {
        let out = k.export_step(&bodies).map_err(e)?;
        let mut k2 = DefaultKernel::new();
        let back = k2.import_step(&out).map_err(e)?;
        let (mut v, mut a, mut solids) = (0.0, 0.0, 0);
        for id in &back {
            let m = k2.mass_properties(*id).map_err(e)?;
            v += m.volume;
            a += m.surface_area;
            solids += k2.get(*id).map_err(e)?.solids().len();
        }
        Ok((v, a, solids))
    }, |r| json!({"volume": r.0, "area": r.1, "solids": r.2}));
    op("mesh", json!({}), || {
        let mut tris = 0;
        for id in &bodies {
            let bb = k.bounding_box(*id).map_err(e)?;
            let q = Tessellation { deflection: (bb.max - bb.min).norm() * 1e-3, ..Tessellation::default() };
            tris += k.tessellate(*id, q).map_err(e)?.indices.len();
        }
        Ok(tris)
    }, |t| json!({"triangles": t}));

    // The operations act on the largest solid body, by its volume.
    let target = bodies.iter().zip(&masses)
        .filter(|(id, _)| k.get(**id).map(|b| !b.solids().is_empty()).unwrap_or(false))
        .filter_map(|(id, m)| m.map(|m| (*id, m)))
        .max_by(|a, b| a.1.total_cmp(&b.1)).map(|x| x.0);
    let Some(target) = target else { return };
    // The sizes of ops.Size, from the target's exact volume and centroid.
    let Ok(m) = k.mass_properties(target) else { return };
    let length = m.volume.abs().cbrt();
    let ball_radius = (3.0 * m.volume.abs() / (4.0 * std::f64::consts::PI)).cbrt();
    let centre: Point3<f64> = m.center_of_mass;

    op("boolean", json!({}), || {
        let ball = k.primitive(&Primitive::Sphere { center: centre, radius: ball_radius, axis: Vector3::z_axis(), seam: Vector3::x_axis() }).map_err(e)?;
        let ball = *ball.bodies.first().ok_or("no ball")?;
        let r = k.boolean(BoolOp::Subtract, target, &[ball]).map_err(e)?;
        let (mut v, mut ok, mut solids) = (0.0, true, 0);
        for id in &r.bodies {
            v += k.mass_properties(*id).map_err(e)?.volume;
            ok &= valid(&k, *id)?;
            solids += k.get(*id).map_err(e)?.solids().len();
        }
        Ok((ok, v, solids))
    }, |r| json!({"valid": r.0, "volume": r.1, "solids": r.2}));

    // Edges a fillet could be asked of: between two different faces, not degenerate.
    let candidates: Vec<EdgeId> = match (k.edges(target), k.get(target)) {
        (Ok(infos), Ok(body)) => infos.iter()
            .filter(|i| matches!(i.faces, [Some(a), Some(b)] if a != b))
            .filter(|i| body.edges().get(i.id.0 as usize).map(|x| !x.degenerate).unwrap_or(false))
            .map(|i| i.id).collect(),
        _ => vec![],
    };
    for i in pick(candidates.len(), FILLETS, &path) {
        let edge = candidates[i];
        op("fillet", json!({"edge": edge.0}), || {
            let r = k.fillet(target, &[edge], length / 100.0).map_err(e)?;
            let id = *r.bodies.first().ok_or("no body")?;
            Ok((valid(&k, id)?, k.mass_properties(id).map_err(e)?.volume))
        }, |r| json!({"valid": r.0, "volume": r.1}));
    }

    if let Ok(faces) = k.faces(target) {
        if let Some(f) = faces.iter().filter(|f| f.kind == SurfaceKind::Plane).max_by(|a, b| a.area.total_cmp(&b.area)) {
            let fid = f.id;
            op("shell", json!({}), || {
                let r = k.shell(target, &[fid], length / 50.0).map_err(e)?;
                let id = *r.bodies.first().ok_or("no body")?;
                Ok((valid(&k, id)?, k.mass_properties(id).map_err(e)?.volume))
            }, |r| json!({"valid": r.0, "volume": r.1}));
        }
    }
}
