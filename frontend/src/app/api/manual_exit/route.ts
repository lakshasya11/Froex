import { NextResponse } from 'next/server';
import { exec } from 'child_process';
import { promisify } from 'util';
import path from 'path';

const execAsync = promisify(exec);

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { ticket } = body;

    if (!ticket) {
      return NextResponse.json({ success: false, error: 'Invalid ticket' }, { status: 400 });
    }

    const cwdPath = path.resolve(process.cwd(), '../backend');
    
    // Command: python manual_exit.py [ticket]
    const command = `python manual_exit.py ${ticket}`;
    
    console.log(`Executing manual exit: ${command} in ${cwdPath}`);

    const { stdout, stderr } = await execAsync(command, { 
      cwd: cwdPath,
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
    });

    if (stderr && stderr.includes('Error')) {
       console.error("Manual exit stderr:", stderr);
    }

    return NextResponse.json({ 
      success: true, 
      output: stdout,
      error: stderr
    });
  } catch (error: any) {
    console.error("Failed to execute manual exit:", error);
    return NextResponse.json({ success: false, error: error.message || 'Execution failed' }, { status: 500 });
  }
}
