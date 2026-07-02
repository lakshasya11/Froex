import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execAsync = promisify(exec);

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { direction, count, lotSize, sl, tp } = body;

    if (!direction || !['BUY', 'SELL'].includes(direction)) {
      return NextResponse.json({ success: false, error: 'Invalid direction' }, { status: 400 });
    }

    // Default values if not provided
    const safeCount = count || 1;
    const safeLotSize = lotSize || 0.05;
    const safeSl = sl || 10.00;
    const safeTp = tp || 3.00;

    // The frontend is in E:\Forex_US\Forex5M-2\frontend
    // We want the cwd to be the backend directory where manual.py is located.
    const cwdPath = path.resolve(process.cwd(), '../backend');
    
    // Command: python manual.py buy 1 0.05 10 3
    const command = `python manual.py ${direction} ${safeCount} ${safeLotSize} ${safeSl} ${safeTp}`;
    
    console.log(`Executing manual trade: ${command} in ${cwdPath}`);

    const { stdout, stderr } = await execAsync(command, { 
      cwd: cwdPath,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    });

    if (stderr && stderr.includes('Error')) {
       console.error("Manual execution stderr:", stderr);
    }

    return NextResponse.json({ 
      success: true, 
      output: stdout,
      error: stderr
    });
  } catch (error: any) {
    console.error("Failed to execute manual trade:", error);
    return NextResponse.json({ success: false, error: error.message || 'Execution failed' }, { status: 500 });
  }
}
