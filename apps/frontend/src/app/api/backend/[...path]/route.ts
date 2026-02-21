/**
 * Catch-all proxy route: forwards /api/backend/** to the FastAPI backend.
 * Eliminates browser CORS issues — all requests appear same-origin to the client.
 */

import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://backend:8000";

type Params = Promise<{ path: string[] }>;

async function proxy(
  request: NextRequest,
  { params }: { params: Params }
) {
  const { path } = await params;
  const pathStr = path.join("/");
  const search = request.nextUrl.search;
  const url = `${BACKEND_URL}/${pathStr}${search}`;

  const isBodyMethod = ["POST", "PUT", "PATCH"].includes(request.method);
  const body = isBodyMethod ? await request.text() : undefined;

  const upstream = await fetch(url, {
    method: request.method,
    headers: { "Content-Type": "application/json" },
    body,
  });

  const data = await upstream.json().catch(() => null);
  return NextResponse.json(data, { status: upstream.status });
}

export const GET = proxy;
export const POST = proxy;
