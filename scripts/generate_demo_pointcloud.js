/**
 * generate_demo_pointcloud.js — create a synthetic demo point cloud
 * (a sphere plus a ground plane, ~50k coloured points) for local testing.
 *
 * Outputs into data/pointclouds/demo-sphere/:
 *   - points.xyz      plain "x y z r g b" text, one point per line
 *   - metadata.json   Potree 2.0-style metadata describing the cloud
 *
 * Run: node scripts/generate_demo_pointcloud.js
 * (Normally invoked by scripts/download_samples.sh step 3.)
 */
const fs = require('fs');

const outDir = '/workspace/data/pointclouds/demo-sphere';
// Potree 2.0 layout expects an octree chunk directory alongside metadata.json;
// we only create the (empty) directory — no actual LAZ chunks are written.
fs.mkdirSync(outDir + '/octree.laz.chunks', { recursive: true });

// Generate points: sphere (30k) + ground (20k)
const points = [];
// Sphere
for (let i = 0; i < 30000; i++) {
  const theta = Math.random() * Math.PI * 2;
  const phi = Math.acos(2 * Math.random() - 1);
  const r = 5 + (Math.random() - 0.5) * 0.3;
  points.push({
    x: r * Math.sin(phi) * Math.cos(theta),
    y: r * Math.sin(phi) * Math.sin(theta),
    z: r * Math.cos(phi),
    r: Math.floor(100 + 155 * Math.abs(Math.sin(phi))),
    g: Math.floor(100 + 155 * Math.abs(Math.cos(theta))),
    b: Math.floor(150 + 105 * Math.random()),
  });
}
// Ground plane
for (let i = 0; i < 20000; i++) {
  points.push({
    x: (Math.random() - 0.5) * 20,
    y: (Math.random() - 0.5) * 20,
    z: -5 + (Math.random() - 0.5) * 0.1,
    r: Math.floor(80 + 60 * Math.random()),
    g: Math.floor(100 + 80 * Math.random()),
    b: Math.floor(60 + 40 * Math.random()),
  });
}

// Write as simple XYZ CSV for human readability + metadata.json for Potree
const csv = points.map(p => `${p.x.toFixed(4)} ${p.y.toFixed(4)} ${p.z.toFixed(4)} ${p.r} ${p.g} ${p.b}`).join('\n');
fs.writeFileSync(outDir + '/points.xyz', csv);

// Potree 2.0 metadata.json
const metadata = {
  version: "2.0",
  name: "Demo Sphere",
  description: "Synthetic demo point cloud — sphere + ground plane, 50k points",
  points: points.length,
  projection: "",
  hierarchy: { firstChunkSize: points.length, stepSize: 4, depth: 1 },
  offset: [0, 0, 0],
  scale: [0.001, 0.001, 0.001],
  spacing: 0.5,
  boundingBox: {
    min: [-10.5, -10.5, -5.5],
    max: [10.5, 10.5, 5.5]
  },
  encoding: "DEFAULT",
  attributes: [
    { name: "position", description: "", size: 12, numElements: 3, elementSize: 4, type: "int32", min: [-10500, -10500, -5500], max: [10500, 10500, 5500] },
    { name: "rgba", description: "", size: 4, numElements: 4, elementSize: 1, type: "uint8", min: [0,0,0,255], max: [255,255,255,255] }
  ]
};
fs.writeFileSync(outDir + '/metadata.json', JSON.stringify(metadata, null, 2));

console.log(`Generated ${points.length} points -> ${outDir}`);
console.log('Files: metadata.json, points.xyz');
