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
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-xl bg-[#2F7D68]/15 border border-[#2F7D68]/30 flex items-center justify-center text-[#2F7D68] dark:text-[#3DA88D]">
              <Users className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-base text-[#252A2B] dark:text-[#F4EFE6]">Multi-Agent Research Committee</h3>
              <div className="flex items-center gap-2 text-xs text-[#77736C] dark:text-[#9E988E]">
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
            <div className="text-[11px] text-[#77736C] dark:text-[#9E988E] uppercase font-semibold">Committee Verdict</div>
            <div className="text-base font-extrabold font-mono text-[#287A50] dark:text-[#34A86E] flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-[#287A50] dark:bg-[#34A86E] animate-pulse" />
              <span>{committee.overall_verdict.replace('_', ' ')}</span>
            </div>
          </div>

          <div className="pl-4 border-l border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 text-right">
            <div className="text-[11px] text-[#77736C] dark:text-[#9E988E] uppercase font-semibold">Consensus Score</div>
            <div className="text-2xl font-black font-mono text-[#2F7D68] dark:text-[#3DA88D]">
              {committee.consensus_score}%
            </div>
          </div>
        </div>
      </div>

      {/* 2. Confidence Calibration Strip (Brier Score & ECE) */}
      <div className="p-4 rounded-2xl bg-[#E7E0D5]/40 dark:bg-[#1C2022]/60 border border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-[#2F7D68] dark:text-[#3DA88D] flex-shrink-0" />
          <div>
            <span className="font-bold text-[#252A2B] dark:text-[#F4EFE6]">Model Confidence Calibration:</span>
            <span className="text-[#77736C] dark:text-[#9E988E] ml-1.5">
              Brier Score: <strong className="font-mono text-[#252A2B] dark:text-[#F4EFE6]">{committee.confidence_calibration.brier_score}</strong>
            </span>
            <span className="text-[#77736C] dark:text-[#9E988E] mx-1.5">•</span>
            <span className="text-[#77736C] dark:text-[#9E988E]">
              Expected Calibration Error (ECE): <strong className="font-mono text-[#252A2B] dark:text-[#F4EFE6]">{committee.confidence_calibration.expected_calibration_error}</strong>
            </span>
          </div>
        </div>

        <span className="px-2.5 py-0.5 rounded-full font-bold text-[10px] bg-[#287A50]/15 text-[#287A50] dark:text-[#34A86E] border border-[#287A50]/30 self-start sm:self-auto">
          {committee.confidence_calibration.calibration_rating}
        </span>
      </div>

      {/* 3. Red-Team / Disconfirmation Highlight Box */}
      <div className="p-4 rounded-2xl bg-[#C64C4C]/5 border border-[#C64C4C]/20 space-y-1.5 text-xs">
        <div className="flex items-center gap-2 text-[#C64C4C] dark:text-[#E05C5C] font-bold">
          <Flame className="w-4 h-4 flex-shrink-0" />
          <span>Red-Team Disconfirmation (Devil&apos;s Advocate Counter-Hypothesis)</span>
        </div>
        <p className="text-[#77736C] dark:text-[#9E988E] leading-relaxed">
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
              className={`p-4 rounded-2xl border transition-all cursor-pointer ${
                isExpanded ? 'border-[#2F7D68] bg-[#FFFCF6] dark:bg-[#1C2022] shadow-sm' : 'border-[#DDD5C9] dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 hover:bg-[#FFFCF6]'
              }`}
              onClick={() => setExpandedAgent(isExpanded ? null : key)}
            >
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2.5">
                  <div className={`p-2 rounded-xl bg-[#E7E0D5]/50 dark:bg-[#141718] border border-[#DDD5C9]/60 ${color}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="font-bold text-xs text-[#252A2B] dark:text-[#F4EFE6]">{agent.name}</div>
                    <div className="text-[10px] text-[#77736C] dark:text-[#9E988E]">{agent.role}</div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded-full font-bold border ${
                      isBull
                        ? 'bg-[#287A50]/15 text-[#287A50] dark:text-[#34A86E] border-[#287A50]/30'
                        : isBear
                        ? 'bg-[#C64C4C]/15 text-[#C64C4C] dark:text-[#E05C5C] border-[#C64C4C]/30'
                        : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                    }`}
                  >
                    {agent.stance} ({agent.confidence}%)
                  </span>
                  {isExpanded ? <ChevronUp className="w-3.5 h-3.5 text-[#77736C]" /> : <ChevronDown className="w-3.5 h-3.5 text-[#77736C]" />}
                </div>
              </div>

              <p className="text-xs text-[#77736C] dark:text-[#9E988E] mt-3 leading-relaxed">
                {agent.summary}
              </p>

              {isExpanded && (
                <div className="mt-3 pt-3 border-t border-[#DDD5C9]/60 dark:border-[#DDD5C9]/15 space-y-2 text-xs">
                  <div className="font-semibold text-[#252A2B] dark:text-[#F4EFE6] text-[11px] uppercase tracking-wider">Key Factors:</div>
                  <ul className="space-y-1 text-[#77736C] dark:text-[#9E988E]">
                    {agent.key_factors.map((factor, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <span className="text-[#2F7D68] mt-0.5">•</span>
                        <span>{factor}</span>
                      </li>
                    ))}
                  </ul>

                  {agent.evidence_citations && agent.evidence_citations.length > 0 && (
                    <div className="pt-2 text-[10px] text-[#77736C] dark:text-[#9E988E]">
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
