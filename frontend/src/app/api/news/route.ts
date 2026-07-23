import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const backendPath = path.resolve(process.cwd(), '../backend');
    const newsPath = path.join(backendPath, 'news_cache.json');
    const configPath = path.join(backendPath, 'config.py');

    // Default config values
    let isEnabled = false;
    let preMinutes = 15;
    let postMinutes = 10;
    let targetCurrency = 'USD';

    // Parse config.py
    if (fs.existsSync(configPath)) {
      const configText = fs.readFileSync(configPath, 'utf-8');
      const parseValue = (key: string, type: 'bool' | 'int' | 'str') => {
        const regex = new RegExp(`^${key}\\s*=\\s*(.+)`, 'm');
        const match = configText.match(regex);
        if (match) {
          const val = match[1].split('#')[0].trim();
          if (type === 'bool') return val === 'True';
          if (type === 'int') return parseInt(val, 10);
          if (type === 'str') return val.replace(/['"]/g, '');
        }
        return null;
      };

      const parsedEnabled = parseValue('ENABLE_NEWS_FILTER', 'bool');
      if (parsedEnabled !== null) isEnabled = parsedEnabled as boolean;

      const parsedPre = parseValue('NEWS_BLOCK_PRE_MINUTES', 'int');
      if (parsedPre !== null) preMinutes = parsedPre as number;

      const parsedPost = parseValue('NEWS_BLOCK_POST_MINUTES', 'int');
      if (parsedPost !== null) postMinutes = parsedPost as number;

      const parsedCurr = parseValue('NEWS_TARGET_CURRENCY', 'str');
      if (parsedCurr !== null) targetCurrency = parsedCurr as string;

      const parsedBlockTrades = parseValue('BLOCK_TRADES_ON_NEWS', 'bool');
      if (parsedBlockTrades !== null && !(parsedBlockTrades as boolean)) {
          // If block is explicitly false, don't block
          preMinutes = -1;
          postMinutes = -1;
      }
    }

    if (!fs.existsSync(newsPath)) {
      return NextResponse.json({
        success: true,
        enabled: isEnabled,
        status: 'INACTIVE',
        reason: 'News cache not found',
        events: []
      });
    }

    const newsData = JSON.parse(fs.readFileSync(newsPath, 'utf-8'));
    
    // Filter for today's high impact USD events
    const now = new Date();
    const todayStr = now.toISOString().split('T')[0];
    
    const relevantEvents = newsData.filter((e: any) => {
      return e.country === targetCurrency;
    });

    // Determine current block status
    let isBlocked = false;
    let blockReason = "";
    let nextEvent = null;

    if (isEnabled) {
      for (const event of relevantEvents) {
        if (event.impact !== 'High') continue; // Only block on HIGH impact
        
        const eventDate = new Date(event.date);
        const diffMs = now.getTime() - eventDate.getTime();
        const diffSeconds = diffMs / 1000;

        // Future
        if (diffSeconds < 0) {
          if (Math.abs(diffSeconds) <= preMinutes * 60) {
            isBlocked = true;
            blockReason = event.title;
            break;
          }
        } 
        // Past
        else {
          if (diffSeconds <= postMinutes * 60) {
            isBlocked = true;
            blockReason = event.title;
            break;
          }
        }
      }
    }

    // Find next upcoming High impact event for the 'Next High Impact Event' banner
    const upcoming = relevantEvents
      .filter((e: any) => e.impact === 'High' && new Date(e.date).getTime() > now.getTime())
      .sort((a: any, b: any) => new Date(a.date).getTime() - new Date(b.date).getTime());
      
    if (upcoming.length > 0) {
      nextEvent = upcoming[0];
    }

    return NextResponse.json({
      success: true,
      enabled: isEnabled,
      isBlocked: isBlocked,
      status: isBlocked ? 'BLOCKED' : (isEnabled ? 'ACTIVE' : 'DISABLED'),
      reason: blockReason,
      nextEvent: nextEvent,
      events: relevantEvents
    });

  } catch (error: any) {
    return NextResponse.json({
      success: false,
      error: 'Failed to fetch news',
      details: error.message
    }, { status: 500 });
  }
}
