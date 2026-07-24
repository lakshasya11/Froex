import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execAsync = promisify(exec);
export const dynamic = 'force-dynamic'; // Prevent caching, always fetch latest

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const filter = searchParams.get('filter') || 'today';
    const dateQuery = searchParams.get('date');

    let targetDate = '';
    if (dateQuery && dateQuery.trim() !== '') {
      targetDate = dateQuery;
    }

    const cwdPath = path.resolve(process.cwd(), '../backend');
    const command = `python get_trades.py ${filter} ${targetDate}`;

    const { stdout, stderr } = await execAsync(command, { 
      cwd: cwdPath,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    });

    if (stderr && stderr.includes('Error')) {
      console.error("Database fetch stderr:", stderr);
    }

    // Output is JSON from python script
    const data = JSON.parse(stdout);

    return NextResponse.json(data);
  } catch (error: any) {
    console.error('Database Fetch Error:', error);
    return NextResponse.json({ 
      success: false, 
      error: 'Failed to fetch trades via python wrapper', 
      details: error.message 
    }, { status: 500 });
  }
}
