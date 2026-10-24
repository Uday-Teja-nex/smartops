import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: {
    // Pin the workspace root so stray lockfiles in parent folders are ignored.
    root: path.join(__dirname),
  },
};

export default nextConfig;
