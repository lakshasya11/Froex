import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

const CONFIG_PATH = path.join(process.cwd(), '../backend/user_config.json');

export async function GET() {
  try {
    if (!fs.existsSync(CONFIG_PATH)) {
      // Return empty default if it doesn't exist yet
      return NextResponse.json({});
    }
    const data = fs.readFileSync(CONFIG_PATH, 'utf-8');
    return NextResponse.json(JSON.parse(data));
  } catch (error) {
    console.error('Error reading config:', error);
    return NextResponse.json({ error: 'Failed to read config' }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const configData = await request.json();
    
    // Write to user_config.json
    fs.writeFileSync(CONFIG_PATH, JSON.stringify(configData, null, 4), 'utf-8');
    
    return NextResponse.json({ success: true, message: 'Configuration saved successfully' });
  } catch (error) {
    console.error('Error saving config:', error);
    return NextResponse.json({ error: 'Failed to save config' }, { status: 500 });
  }
}
