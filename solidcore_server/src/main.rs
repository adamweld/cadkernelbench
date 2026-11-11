// SPDX-License-Identifier: MIT OR Apache-2.0

//! Line-oriented JSON server over solidcore-ops, for the robustness
//! benchmark. One request per line on stdin, one reply per line on stdout.
//! It makes kernel calls only; cases and scoring live in the Python side.

use serde_json::{json, Value};
use solidcore_ops::{make_box, make_cone, make_cylinder, make_sphere, make_torus, Body, BooleanOp, CheckLevel, PointClass};
use std::collections::HashMap;
use std::io::{BufRead, Write};

fn f(v: &Value) -> f64 {
    v.as_f64().unwrap_or(f64::NAN)
}

fn v3(v: &Value) -> [f64; 3] {
    [f(&v[0]), f(&v[1]), f(&v[2])]
}

fn handle(req: &Value, bodies: &mut HashMap<u64, Body>, next: &mut u64) -> Value {
    let op = req["op"].as_str().unwrap_or("");
    match op {
        "make" => {
            let p = v3(&req["p"]);
            let d: Vec<f64> = req["dims"].as_array().map(|a| a.iter().map(f).collect()).unwrap_or_default();
            let made = match req["kind"].as_str().unwrap_or("") {
                "box" => make_box(p, [d[0], d[1], d[2]]),
                "cyl" => make_cylinder(p, d[0], d[1]),
                "sph" => make_sphere(p, d[0]),
                "cone" => make_cone(p, d[0], d[1], d[2]),
                "torus" => make_torus(p, d[0], d[1]),
                _ => return json!({"err": "unknown kind"}),
            };
            let body = match made {
                Ok(b) => b,
                Err(e) => return json!({"err": format!("{e:?}")}),
            };
            let mut m = [[0.0f64; 4]; 4];
            for (i, row) in m.iter_mut().enumerate() {
                for (j, x) in row.iter_mut().enumerate() {
                    *x = f(&req["m"][i][j]);
                }
            }
            if let Err(e) = body.transform(&m) {
                return json!({"err": format!("transform {e:?}")});
            }
            *next += 1;
            bodies.insert(*next, body);
            json!({"h": *next})
        }
        "bool" => {
            let (Some(a), Some(b)) = (bodies.get(&req["a"].as_u64().unwrap_or(0)), bodies.get(&req["b"].as_u64().unwrap_or(0))) else {
                return json!({"err": "bad handle"});
            };
            let kind = match req["kind"].as_str().unwrap_or("") {
                "fuse" => BooleanOp::Union,
                "cut" => BooleanOp::Subtract,
                "common" => BooleanOp::Intersect,
                _ => return json!({"err": "unknown op"}),
            };
            // The operation consumes its operands.
            let (ca, cb) = match (a.copy(), b.copy()) {
                (Ok(x), Ok(y)) => (x, y),
                _ => return json!({"status": "error", "err": "copy failed"}),
            };
            match solidcore_ops::boolean::boolean(ca, cb, kind) {
                Ok(None) => json!({"status": "empty"}),
                Ok(Some(r)) => {
                    let vol = r.volume(1e-6).unwrap_or(f64::NAN);
                    *next += 1;
                    bodies.insert(*next, r);
                    json!({"status": "ok", "h": *next, "vol": vol})
                }
                Err(e) => json!({"status": "error", "err": format!("{e:?}")}),
            }
        }
        "valid" => {
            let Some(b) = bodies.get(&req["h"].as_u64().unwrap_or(0)) else { return json!({"err": "bad handle"}) };
            let solid = b.is_manifold_solid().unwrap_or(false);
            let checked = b.check(CheckLevel::Geometry).map(|r| r.is_valid()).unwrap_or(false);
            json!({"valid": solid && checked, "solid": solid, "check": checked})
        }
        "vol" => {
            let Some(b) = bodies.get(&req["h"].as_u64().unwrap_or(0)) else { return json!({"err": "bad handle"}) };
            match b.volume(1e-6) {
                Ok(v) => json!({"vol": v}),
                Err(e) => json!({"err": format!("{e:?}")}),
            }
        }
        "bbox" => {
            let Some(b) = bodies.get(&req["h"].as_u64().unwrap_or(0)) else { return json!({"err": "bad handle"}) };
            match b.bounds() {
                Ok((lo, hi)) => json!({"lo": lo, "hi": hi}),
                Err(e) => json!({"err": format!("{e:?}")}),
            }
        }
        "classify" => {
            let Some(b) = bodies.get(&req["h"].as_u64().unwrap_or(0)) else { return json!({"err": "bad handle"}) };
            let out: Vec<i64> = req["pts"]
                .as_array()
                .map(|a| {
                    a.iter()
                        .map(|p| match b.classify_point(v3(p)) {
                            Ok(PointClass::Inside) => 1,
                            Ok(PointClass::Outside) => 0,
                            Ok(PointClass::OnBoundary) => -1,
                            Err(_) => -2,
                        })
                        .collect()
                })
                .unwrap_or_default();
            json!({"cls": out})
        }
        "free" => {
            if let Some(a) = req["hs"].as_array() {
                for h in a {
                    bodies.remove(&h.as_u64().unwrap_or(0));
                }
            }
            json!({"ok": true})
        }
        _ => json!({"err": "unknown request"}),
    }
}

fn main() {
    let mut bodies: HashMap<u64, Body> = HashMap::new();
    let mut next = 0u64;
    let stdin = std::io::stdin();
    let mut out = std::io::stdout().lock();
    for line in stdin.lock().lines() {
        let Ok(line) = line else { break };
        let reply = match serde_json::from_str::<Value>(&line) {
            Ok(req) => handle(&req, &mut bodies, &mut next),
            Err(e) => json!({"err": format!("bad json: {e}")}),
        };
        if writeln!(out, "{reply}").is_err() || out.flush().is_err() {
            break;
        }
    }
}
