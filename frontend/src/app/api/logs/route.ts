import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const logPath = path.join(process.cwd(), '..', 'backend', 'debug.log');
    if (!fs.existsSync(logPath)) {
      return NextResponse.json({ success: true, logs: 'Awaiting logs from backend terminal...' });
    }
    
    const content = fs.readFileSync(logPath, 'utf-8');
    const lines = content.split('\n');
    // Keep last 1000 lines
    const tail = lines.slice(-1000).join('\n');
    
    return NextResponse.json({ success: true, logs: tail });
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err.message }, { status: 500 });
  }
}
