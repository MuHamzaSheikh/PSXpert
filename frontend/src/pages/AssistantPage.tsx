import React, { useState } from 'react';
import { Card } from '@/components/common/Card';
import { DemoBadge } from '@/components/common/DemoBadge';
import { ChatMessage } from '@/types';
import {
  Bot,
  Send,
  User,
  Sparkles,
  FileText,
  ShieldAlert,
  ExternalLink,
  ChevronRight,
  HelpCircle,
  Clock,
  Layers,
  Database,
} from 'lucide-react';

const SUGGESTED_PROMPTS = [
  'Evaluate Meezan Bank (MEBL) quarterly dividend payout and capital adequacy.',
  'What is the current HMM market regime for E&P stocks (OGDC & PPL)?',
  'Compare cement sector margins under elevated industrial power tariffs.',
  'Analyze Systems Ltd (SYS) recent valuation multiples and export earnings.',
];

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: 'msg_1',
    sender: 'assistant',
    timestamp: '11:30 AM',
    text: `Hello! I am **PSXpert AI Research Assistant**, powered by historical PSX market datasets (2002–2026), official corporate regulatory filings (DPS), and FinBERT transformer sentiment analysis.\n\nAsk me about specific ticker valuations, quantitative indicator regimes, dividend payouts, or sector macroeconomic impacts.`,
  },
  {
    id: 'msg_2',
    sender: 'user',
    timestamp: '11:32 AM',
    text: 'Evaluate Meezan Bank (MEBL) quarterly dividend payout and capital adequacy.',
  },
  {
    id: 'msg_3',
    sender: 'assistant',
    timestamp: '11:32 AM',
    text: `### Meezan Bank Limited (PSX: MEBL) — Q3 2026 Synthesis\n\n1. **Financial Performance & Solvency**:\n   - **Earnings Per Share (EPS)**: PKR 31.42 for the 9-month period ended September 30, 2026.\n   - **Interim Cash Dividend**: PKR 7.00 per share (70% on face value).\n   - **Capital Adequacy Ratio (CAR)**: Reported at **21.4%**, providing a comfortable 9.9% buffer above the State Bank of Pakistan’s mandatory 11.5% regulatory requirement.\n\n2. **Quantitative & Technical Momentum**:\n   - Current closing price is **PKR 248.50**, trading comfortably above both 50-day (236.10) and 200-day (212.40) SMAs.\n   - **RSI (14)** is at **58.4**, showing healthy bullish momentum with ample headroom before overbought territory (70.0).\n\n3. **FinBERT News Tone**:\n   - Sentiment score on banking regulatory revisions is **+0.78 (Positive)**.\n\n> **Notice**: Algorithmic research diagnostic only, not guaranteed advice.`,
    evidence: [
      {
        source: 'PSX DPS Regulatory Disclosure',
        title: 'MEBL Financial Results for 9-Months Ended Sept 30, 2026',
        snippet: 'Board approved interim cash dividend of Rs. 7.00 per share (70%). Profit after tax reported at PKR 48.2 billion.',
        url: 'https://dps.psx.com.pk/download/document/WAS-249475.pdf',
      },
      {
        source: 'State Bank of Pakistan (SBP)',
        title: 'Quarterly Islamic Banking Review 2026',
        snippet: 'Meezan Bank retains highest Islamic deposit share with Non-Performing Financing (NPF) ratio below 1.4%.',
      },
    ],
    confidence_score: 94,
    disclaimer_required: true,
  },
];

export const AssistantPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [inputPrompt, setInputPrompt] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  const handleSend = (textToSend?: string) => {
    const text = textToSend || inputPrompt;
    if (!text.trim()) return;

    const userMsg: ChatMessage = {
      id: `usr_${Date.now()}`,
      sender: 'user',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      text: text.trim(),
    };

    setMessages(prev => [...prev, userMsg]);
    if (!textToSend) setInputPrompt('');
    setIsTyping(true);

    // Simulate RAG multi-agent retrieval response
    setTimeout(() => {
      const assistantMsg: ChatMessage = {
        id: `ast_${Date.now()}`,
        sender: 'assistant',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        text: `### PSXpert Synthesis for "${text.slice(0, 40)}..."\n\n- **Technical Regime**: Momentum indicates constructive accumulation with ADX confirming directional strength.\n- **Fundamental Check**: Balance sheet liquidity is healthy with conservative leverage ratios.\n- **Market Context**: FinBERT sentiment across related Dawn and Business Recorder articles registers net positive.\n\n*Note: This synthesis draws on point-in-time exchange records from 2002 to 2026 with zero lookahead bias.*`,
        evidence: [
          {
            source: 'PSX Historical Technical Dataset',
            title: '25-Year Daily Settlement Series (2002–2026)',
            snippet: 'Zero lookahead indicators computed with Wilder smoothing and verified against manual scalar formulas.',
          },
        ],
        confidence_score: 89,
        disclaimer_required: true,
      };

      setMessages(prev => [...prev, assistantMsg]);
      setIsTyping(false);
    }, 1200);
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto animate-in fade-in duration-300">
      {/* 1. Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-border pb-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-fg">
              AI Research Assistant
            </h1>
            <DemoBadge label="FinBERT + RAG Engine" />
          </div>
          <p className="text-xs sm:text-sm text-fg-muted mt-1">
            Autonomous equity intelligence powered by exchange filings, FinBERT sentiment, and quantitative diagnostics.
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs text-fg-subtle">
          <Database className="w-3.5 h-3.5 text-brand-600" />
          <span>20,800+ Filings Indexed</span>
        </div>
      </div>

      {/* 2. Suggested Prompt Chips */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-fg-subtle font-medium flex items-center gap-1">
          <Sparkles className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400" />
          <span>Suggested:</span>
        </span>
        {SUGGESTED_PROMPTS.map((prompt, i) => (
          <button
            key={i}
            onClick={() => handleSend(prompt)}
            className="px-3 py-1.5 rounded-full bg-bg-elevated/70 border border-border text-fg-muted hover:border-brand-500 hover:text-brand-600 dark:hover:text-brand-400 transition-colors text-left"
          >
            {prompt}
          </button>
        ))}
      </div>

      {/* 3. Main Chat Viewport */}
      <Card className="p-0 overflow-hidden shadow-card flex flex-col h-[600px]">
        {/* Messages Container */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5">
          {messages.map(msg => {
            const isUser = msg.sender === 'user';
            return (
              <div
                key={msg.id}
                className={`flex gap-3 max-w-3xl ${isUser ? 'ml-auto flex-row-reverse' : ''}`}
              >
                {/* Avatar Badge */}
                <div
                  className={`w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0 text-white font-bold text-xs ${
                    isUser
                      ? 'bg-fg-muted'
                      : 'bg-gradient-to-br from-brand-500 to-brand-700 shadow-sm shadow-brand-500/20'
                  }`}
                >
                  {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>

                {/* Message Body */}
                <div className="space-y-2">
                  <div
                    className={`p-4 rounded-2xl text-xs sm:text-sm leading-relaxed ${
                      isUser
                        ? 'bg-brand-500 text-white font-medium rounded-tr-sm shadow-sm'
                        : 'bg-bg-elevated/70 border border-border text-fg rounded-tl-sm'
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{msg.text}</div>
                  </div>

                  {/* Evidence & Citations Panel for AI messages */}
                  {!isUser && msg.evidence && msg.evidence.length > 0 && (
                    <div className="p-3 rounded-xl border border-brand-500/20 bg-brand-500/5 space-y-2 text-xs">
                      <div className="flex items-center justify-between text-brand-600 dark:text-brand-400 font-bold text-[11px] uppercase tracking-wider">
                        <span className="flex items-center gap-1">
                          <FileText className="w-3.5 h-3.5" />
                          <span>Retrieved Evidence & Sources ({msg.evidence.length})</span>
                        </span>
                        {msg.confidence_score && (
                          <span className="font-mono">{msg.confidence_score}% Confidence</span>
                        )}
                      </div>

                      <div className="space-y-1.5 divide-y divide-border/30">
                        {msg.evidence.map((ev, idx) => (
                          <div key={idx} className="pt-1.5 first:pt-0 space-y-0.5">
                            <div className="font-semibold text-fg flex items-center justify-between">
                              <span>{ev.title}</span>
                              {ev.url && (
                                <a
                                  href={ev.url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-brand-600 dark:text-brand-400 flex items-center gap-0.5 hover:underline text-[10px]"
                                >
                                  <span>View DPS PDF</span>
                                  <ExternalLink className="w-2.5 h-2.5" />
                                </a>
                              )}
                            </div>
                            <p className="text-[11px] text-fg-muted italic leading-snug">
                              &ldquo;{ev.snippet}&rdquo;
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex items-center gap-2 text-[10px] text-fg-subtle px-1">
                    <span>{msg.timestamp}</span>
                    {!isUser && <span>• PSXpert Neural RAG Model</span>}
                  </div>
                </div>
              </div>
            );
          })}

          {isTyping && (
            <div className="flex gap-3 max-w-xl">
              <div className="w-8 h-8 rounded-xl bg-brand-500 flex items-center justify-center text-white">
                <Bot className="w-4 h-4 animate-spin" />
              </div>
              <div className="p-3.5 rounded-2xl bg-bg-elevated border border-border text-xs text-fg-muted flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-brand-500 animate-ping" />
                <span>Synthesizing filings & technical evidence...</span>
              </div>
            </div>
          )}
        </div>

        {/* Input Bar */}
        <div className="p-3.5 border-t border-border bg-bg-card">
          <form
            onSubmit={e => {
              e.preventDefault();
              handleSend();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              placeholder="Ask about a PSX stock, dividend payout, or market regime..."
              value={inputPrompt}
              onChange={e => setInputPrompt(e.target.value)}
              className="flex-1 px-4 py-2.5 rounded-xl border border-border bg-bg text-xs sm:text-sm text-fg placeholder:text-fg-subtle outline-none focus:border-brand-500"
            />
            <button
              type="submit"
              disabled={!inputPrompt.trim() || isTyping}
              className="p-2.5 rounded-xl bg-brand-500 hover:bg-brand-600 disabled:opacity-40 text-white font-bold transition-colors"
              aria-label="Send Message"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </Card>
    </div>
  );
};
