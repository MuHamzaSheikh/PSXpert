import React, { useState } from 'react';
import { Card } from '@/components/common/Card';
import { DemoBadge } from '@/components/common/DemoBadge';
import { MultiAgentCommittee, AgentOutput } from '@/types';
import {
  Users,
  ShieldCheck,
  TrendingUp,
  LineChart,
  DollarSign,
  AlertOctagon,
  Globe,
  Flame,
  ChevronDown,
  ChevronUp,
  FileCheck,
  Cpu,
} from 'lucide-react';

interface MultiAgentCommitteePanelProps {
  committee: MultiAgentCommittee;
}

export const MultiAgentCommitteePanel: React.FC<MultiAgentCommitteePanelProps> = ({ committee }) => {
  const [expandedAgent, setExpandedAgent] = useState<string | null>('technical_agent');

  const agentsList = [
    { key: 'data_agent', agent: committee.agents.data_agent, icon: FileCheck, color: 'text-sky-500' },
    { key: 'technical_agent', agent: committee.agents.technical_agent, icon: LineChart, color: 'text-brand-500' },
    { key: 'fundamental_agent', agent: committee.agents.fundamental_agent, icon: DollarSign, color: 'text-emerald-500' },
    { key: 'risk_agent', agent: committee.agents.risk_agent, icon: AlertOctagon, color: 'text-amber-500' },
    { key: 'market_context_agent', agent: committee.agents.market_context_agent, icon: Globe, color: 'text-indigo-500' },
    { key: 'disconfirmation_agent', agent: committee.agents.disconfirmation_agent, icon: Flame, color: 'text-rose-500' },
  ];

  return (
    <Card className="p-6 space-y-6">
      {/* 1. Header with Verdict & Consensus */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-border pb-5">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-brand-500/10 border border-brand-500/20 flex items-center justify-center text-brand-600 dark:text-brand-400">
              <Users className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-base text-fg">Multi-Agent Research Committee</h3>
              <div className="flex items-center gap-2 text-xs text-fg-subtle">
                <span>Autonomous Multi-Agent Deliberation</span>
                <span>•</span>
                <DemoBadge label="Agent Committee Engine" />
              </div>
            </div>
          </div>
        </div>

        {/* Verdict Badge & Score */}
        <div className="flex items-center gap-4 self-start md:self-auto">
          <div className="text-right">
            <div className="text-[11px] text-fg-subtle uppercase font-semibold">Committee Verdict</div>
            <div className="text-base font-extrabold font-mono text-bull flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-bull animate-pulse" />
              <span>{committee.overall_verdict.replace('_', ' ')}</span>
            </div>
          </div>

          <div className="pl-4 border-l border-border text-right">
            <div className="text-[11px] text-fg-subtle uppercase font-semibold">Consensus Score</div>
            <div className="text-2xl font-black font-mono text-brand-600 dark:text-brand-400">
              {committee.consensus_score}%
            </div>
          </div>
        </div>
      </div>

      {/* 2. Confidence Calibration Strip (Brier Score & ECE) */}
      <div className="p-4 rounded-xl bg-bg-elevated/50 border border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-brand-600 dark:text-brand-400 flex-shrink-0" />
          <div>
            <span className="font-bold text-fg">Model Confidence Calibration:</span>
            <span className="text-fg-muted ml-1.5">
              Brier Score: <strong className="font-mono text-fg">{committee.confidence_calibration.brier_score}</strong>
            </span>
            <span className="text-fg-subtle mx-1.5">•</span>
            <span className="text-fg-muted">
              Expected Calibration Error (ECE): <strong className="font-mono text-fg">{committee.confidence_calibration.expected_calibration_error}</strong>
            </span>
          </div>
        </div>

        <span className="px-2.5 py-0.5 rounded-full font-bold text-[10px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 self-start sm:self-auto">
          {committee.confidence_calibration.calibration_rating}
        </span>
      </div>

      {/* 3. Red-Team / Disconfirmation Highlight Box */}
      <div className="p-4 rounded-xl bg-rose-500/5 border border-rose-500/20 space-y-1.5 text-xs">
        <div className="flex items-center gap-2 text-rose-500 font-bold">
          <Flame className="w-4 h-4 flex-shrink-0" />
          <span>Red-Team Disconfirmation (Devil&apos;s Advocate Counter-Hypothesis)</span>
        </div>
        <p className="text-fg-muted leading-relaxed">
          {committee.disconfirmation_notes}
        </p>
      </div>

      {/* 4. Specialist Agents Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {agentsList.map(({ key, agent, icon: Icon, color }) => {
          const isExpanded = expandedAgent === key;
          const isBull = agent.stance === 'BULLISH';
          const isBear = agent.stance === 'BEARISH';

          return (
            <div
              key={key}
              className={`p-4 rounded-xl border transition-all cursor-pointer ${
                isExpanded ? 'border-brand-500 bg-bg-elevated/80' : 'border-border bg-bg-card hover:bg-bg-elevated/40'
              }`}
              onClick={() => setExpandedAgent(isExpanded ? null : key)}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2.5">
                  <div className={`p-2 rounded-lg bg-bg border border-border ${color}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="font-bold text-xs text-fg">{agent.name}</div>
                    <div className="text-[10px] text-fg-subtle">{agent.role}</div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
                      isBull
                        ? 'bg-bull-bg text-bull border-bull/30'
                        : isBear
                        ? 'bg-bear-bg text-bear border-bear/30'
                        : 'bg-amber-500/10 text-amber-500 border-amber-500/20'
                    }`}
                  >
                    {agent.stance} ({agent.confidence}%)
                  </span>
                  {isExpanded ? <ChevronUp className="w-3.5 h-3.5 text-fg-subtle" /> : <ChevronDown className="w-3.5 h-3.5 text-fg-subtle" />}
                </div>
              </div>

              <p className="text-xs text-fg-muted mt-3 leading-relaxed">
                {agent.summary}
              </p>

              {isExpanded && (
                <div className="mt-3 pt-3 border-t border-border/60 space-y-2 text-xs">
                  <div className="font-semibold text-fg text-[11px] uppercase tracking-wider">Key Factors:</div>
                  <ul className="space-y-1 text-fg-muted">
                    {agent.key_factors.map((factor, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <span className="text-brand-500 mt-0.5">•</span>
                        <span>{factor}</span>
                      </li>
                    ))}
                  </ul>

                  {agent.evidence_citations && agent.evidence_citations.length > 0 && (
                    <div className="pt-2 text-[10px] text-fg-subtle">
                      <strong>Citations:</strong> {agent.evidence_citations.join('; ')}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
};
