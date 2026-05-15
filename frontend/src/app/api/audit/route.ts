import { NextRequest, NextResponse } from "next/server";

const API_BASE = "https://sublime-illumination-production-5373.up.railway.app";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    const res = await fetch(`${API_BASE}/api/v1/audit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Audit failed" },
      { status: 500 }
    );
  }
}