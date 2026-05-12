import { NextRequest, NextResponse } from "next/server";
import { appendFile, mkdir } from "fs/promises";
import { join } from "path";
import { existsSync } from "fs";

const WAITLIST_FILE = join(process.cwd(), "waitlist.json");

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const email = (body.email || "").trim().toLowerCase();

    if (!email || !email.includes("@")) {
      return NextResponse.json(
        { detail: "Valid email required" },
        { status: 400 }
      );
    }

    // Check for duplicates
    let existing = "[]";
    try {
      const { readFile } = await import("fs/promises");
      existing = await readFile(WAITLIST_FILE, "utf-8");
    } catch {}

    const entries = JSON.parse(existing || "[]");
    if (entries.includes(email)) {
      return NextResponse.json({ message: "Already on waitlist!" });
    }

    entries.push(email);
    const { writeFile } = await import("fs/promises");
    await writeFile(WAITLIST_FILE, JSON.stringify(entries, null, 2));

    return NextResponse.json({ message: "Added to waitlist!" });
  } catch (error) {
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : "Failed" },
      { status: 500 }
    );
  }
}