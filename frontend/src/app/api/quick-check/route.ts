import { NextRequest, NextResponse } from "next/server";

const API_BASE = "https://sublime-illumination-production-5373.up.railway.app";

export async function POST(request: NextRequest) {
  try {
    const url = request.nextUrl.searchParams.get("url");
    if (!url) {
      return NextResponse.json({ detail: "Missing url parameter" }, { status: 400 });
    }

    const res = await fetch(`${API_BASE}/api/quick-check?url=${encodeURIComponent(url)}`, {
      method: "POST",
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Check failed" },
      { status: 500 }
    );
  }
}