import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic'; // Prevent caching, always fetch latest

export async function GET() {
  try {
    const jsonPath = path.resolve(process.cwd(), '../backend/active_trade.json');
    
    let marketState = null;
    const statePath = path.resolve(process.cwd(), '../backend/market_state.json');
    if (fs.existsSync(statePath)) {
      try {
        marketState = JSON.parse(fs.readFileSync(statePath, 'utf8'));
      } catch(e) {}
    }

    if (!fs.existsSync(jsonPath)) {
      return NextResponse.json({ success: true, activeTrade: null, marketState });
    }
    
    const data = fs.readFileSync(jsonPath, 'utf8');
    
    if (!data || data.trim() === 'null') {
      return NextResponse.json({ success: true, activeTrade: null, marketState });
    }
    
    let activeTrade = null;
    if (data && data.trim() !== 'null') {
      activeTrade = JSON.parse(data);
    }
    

    return NextResponse.json({ success: true, activeTrade, marketState });
    
  } catch (error: any) {
    console.error('Active Trade Fetch Error:', error);
    return NextResponse.json({ 
      success: false, 
      activeTrade: null,
      error: 'Failed to fetch active trade'
    }, { status: 500 });
  }
}
