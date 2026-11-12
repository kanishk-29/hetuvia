"use client";

import { useEffect, useState } from "react";
import { fetchHealth } from "@/lib/api/health";

export default function Home() {
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");

  useEffect(() => {
    fetchHealth()
      .then(() => setStatus("ok"))
      .catch(() => setStatus("error"));
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4">
      <h1 className="text-3xl font-semibold">HETUVIA</h1>
      <p className="text-gray-600">Preventive care coordination (prototype)</p>
      <p>
        API:{" "}
        <span className={status === "ok" ? "text-green-600" : "text-red-600"}>
          {status === "loading" ? "checking..." : status === "ok" ? "OK" : "unreachable"}
        </span>
      </p>
    </main>
  );
}