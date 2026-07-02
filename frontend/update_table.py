import sys

file_path = "src/app/page.tsx"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add expandedRow state
content = content.replace("const [loading, setLoading] = useState(true);", "const [loading, setLoading] = useState(true);\n  const [expandedRow, setExpandedRow] = useState<number | null>(null);")

# 2. Update the table body row map
old_tbody = """              <tbody>
                {filteredTrades.map((t) => (
                  <tr key={t.id} className="border-b border-slate-100 hover:bg-slate-50/50 transition-colors">
                    <td className="p-4 text-sm font-medium text-slate-900 whitespace-nowrap">
                      <div>{t.entry_time.split(' ')[0]}</div>
                      <div className="text-slate-500 text-xs">{t.entry_time.split(' ')[1]}</div>
                    </td>
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${t.direction === 'BUY' ? 'bg-blue-500' : 'bg-fuchsia-500'}`}></span>
                        <span className={`text-sm font-bold ${t.direction === 'BUY' ? 'text-blue-600' : 'text-fuchsia-600'}`}>
                          {t.direction}
                        </span>
                      </div>
                    </td>
                    <td className="p-4 text-sm text-slate-900 font-medium">{t.volume.toFixed(2)}</td>
                    <td className="p-4 text-sm font-mono text-slate-600">{t.entry_price.toFixed(5)}</td>
                    <td className="p-4 text-sm font-mono text-slate-600">{t.exit_price.toFixed(5)}</td>
                    <td className="p-4 text-xs font-medium text-slate-500 max-w-[150px] truncate" title={t.exit_reason}>
                      {t.exit_reason}
                    </td>
                    <td className={`p-4 text-sm font-bold ${t.profit_points >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {t.profit_points >= 0 ? '+' : ''}{t.profit_points.toFixed(1)}
                    </td>
                    <td className={`p-4 text-sm font-black ${t.profit_dollars >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {t.profit_dollars >= 0 ? '+' : ''}${t.profit_dollars.toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>"""

new_tbody = """              <tbody>
                {filteredTrades.map((t) => (
                  <React.Fragment key={t.id}>
                    <tr 
                      onClick={() => setExpandedRow(expandedRow === t.id ? null : t.id)}
                      className={`border-b border-slate-100 transition-colors cursor-pointer ${t.profit_dollars > 0 ? 'hover:bg-emerald-50/50 bg-emerald-50/10' : t.profit_dollars < 0 ? 'hover:bg-rose-50/50 bg-rose-50/10' : 'hover:bg-slate-50/50'}`}
                    >
                      <td className="p-4 text-sm font-medium text-slate-900 whitespace-nowrap">
                        <div>{t.entry_time.split(' ')[0]}</div>
                        <div className="text-slate-500 text-xs">{t.entry_time.split(' ')[1]}</div>
                      </td>
                      <td className="p-4">
                        <div className="flex items-center gap-2">
                          <span className={`w-2 h-2 rounded-full ${t.direction === 'BUY' ? 'bg-blue-500' : 'bg-fuchsia-500'}`}></span>
                          <span className={`text-sm font-bold ${t.direction === 'BUY' ? 'text-blue-600' : 'text-fuchsia-600'}`}>
                            {t.direction}
                          </span>
                        </div>
                      </td>
                      <td className="p-4 text-sm text-slate-900 font-medium">{t.volume.toFixed(2)}</td>
                      <td className="p-4 text-sm font-mono text-slate-600">{t.entry_price.toFixed(5)}</td>
                      <td className="p-4 text-sm font-mono text-slate-600">{t.exit_price.toFixed(5)}</td>
                      <td className="p-4 text-xs font-medium text-slate-500 max-w-[150px] truncate" title={t.exit_reason}>
                        {t.exit_reason}
                      </td>
                      <td className={`p-4 text-sm font-bold ${t.profit_points >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                        {t.profit_points >= 0 ? '+' : ''}{t.profit_points.toFixed(1)}
                      </td>
                      <td className={`p-4 text-sm font-black ${t.profit_dollars >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                        {t.profit_dollars >= 0 ? '+' : ''}${t.profit_dollars.toFixed(2)}
                      </td>
                    </tr>
                    {expandedRow === t.id && (
                      <tr className="bg-slate-50/80 border-b border-slate-200">
                        <td colSpan={8} className="p-4">
                          <div className="flex flex-col md:flex-row gap-6 p-4 bg-white rounded-xl border border-slate-200 shadow-inner">
                            <div className="flex-1">
                              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Exit Reason</h4>
                              <p className="text-sm font-medium text-slate-900 bg-slate-100 p-3 rounded-lg border border-slate-200">
                                {t.exit_reason}
                              </p>
                            </div>
                            <div className="flex-1">
                              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-widest mb-2">Trade Details</h4>
                              <div className="grid grid-cols-2 gap-4">
                                <div>
                                  <span className="text-xs text-slate-500 block">Exit Time</span>
                                  <span className="text-sm font-bold text-slate-900">{t.exit_time}</span>
                                </div>
                                <div>
                                  <span className="text-xs text-slate-500 block">Stop Loss</span>
                                  <span className="text-sm font-bold text-slate-900">{t.sl.toFixed(5)}</span>
                                </div>
                                <div>
                                  <span className="text-xs text-slate-500 block">Ticket ID</span>
                                  <span className="text-sm font-bold text-slate-900">#{t.ticket}</span>
                                </div>
                                <div>
                                  <span className="text-xs text-slate-500 block">Take Profit</span>
                                  <span className="text-sm font-bold text-slate-900">{t.tp.toFixed(5)}</span>
                                </div>
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>"""

# need to import React if not imported
if "import React" not in content:
    content = content.replace("import { useEffect, useState } from 'react';", "import React, { useEffect, useState } from 'react';")

content = content.replace(old_tbody, new_tbody)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Done")
