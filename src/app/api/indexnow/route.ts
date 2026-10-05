import { NextRequest, NextResponse } from "next/server";

const INDEXNOW_KEY = "30a54c7d407506e11670f0bec5ac1238";
const HOST = "cloudfinops.solutions";

export async function POST(request: NextRequest) {
  const authHeader = request.headers.get("authorization");
  if (authHeader !== `Bearer ${process.env.INDEXNOW_SECRET}`) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { urls } = await request.json();
  const urlList = Array.isArray(urls) ? urls : [urls];

  const payload = {
    host: HOST,
    key: INDEXNOW_KEY,
    keyLocation: `https://${HOST}/${INDEXNOW_KEY}.txt`,
    urlList: urlList.map((u: string) =>
      u.startsWith("http") ? u : `https://${HOST}${u}`
    ),
  };

  const response = await fetch("https://api.indexnow.org/indexnow", {
    method: "POST",
    headers: { "Content-Type": "application/json; charset=utf-8" },
    body: JSON.stringify(payload),
  });

  return NextResponse.json({
    success: response.ok,
    status: response.status,
    submitted: urlList.length,
  });
}
