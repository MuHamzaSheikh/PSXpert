import React, { useState, useEffect, useRef } from 'react';
import { NavLink, Link, useNavigate, useLocation } from 'react-router-dom';
import {
  TrendingUp,
  Search,
  SlidersHorizontal,
  LineChart,
  Briefcase,
  Bot,
  FileText,
  Star,
  Settings,
  Menu,
  X,
  ChevronDown,
} from 'lucide-react';
import { ThemeToggle } from '@/components/common/ThemeToggle';
import { MarketStatusBar } from './MarketStatusBar';
import { GlobalSearchModal } from './GlobalSearchModal';

interface NavItem {
  name: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  isNew?: boolean;
}

export const Navbar: React.FC = () => {
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isMoreMenuOpen, setIsMoreMenuOpen] = useState(false);
  const moreMenuRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const location = useLocation();

  // Close mobile drawer and more menu on route change
  useEffect(() => {
    setIsMobileMenuOpen(false);
    setIsMoreMenuOpen(false);
  }, [location.pathname]);

  // Click outside listener for "More" dropdown
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (moreMenuRef.current && !moreMenuRef.current.contains(e.target as Node)) {
        setIsMoreMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Global keydown listener for Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        setIsSearchOpen(true);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const primaryLinks: NavItem[] = [
    { name: 'Dashboard', path: '/', icon: TrendingUp },
    { name: 'AI Screener', path: '/screener', icon: SlidersHorizontal },
    { name: 'Analysis', path: '/analysis', icon: LineChart },
    { name: 'Portfolio', path: '/portfolio', icon: Briefcase },
  ];

  const secondaryLinks: NavItem[] = [
    { name: 'AI Assistant', path: '/assistant', icon: Bot, isNew: true },
    { name: 'Research', path: '/insights', icon: FileText },
    { name: 'Watchlist', path: '/watchlist', icon: Star },
  ];

  const allNavLinks = [...primaryLinks, ...secondaryLinks];

  // Check if any secondary link is currently active
  const isSecondaryActive = secondaryLinks.some(link => location.pathname.startsWith(link.path));

  return (
    <>
      <header className="sticky top-0 z-40 w-full bg-bg-card/95 backdrop-blur-md border-b border-border shadow-subtle overflow-x-clip">
        {/* Upper Top Status Strip */}
        <MarketStatusBar />

        {/* Main Nav Header */}
        <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-2 sm:gap-4 w-full">
          {/* 1. Left: Brand Logo & Optional Search Bar */}
          <div className="flex items-center gap-2 sm:gap-4 flex-shrink-0">
            <Link to="/" className="flex items-center gap-2 flex-shrink-0 group">
              <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-white shadow-sm shadow-brand-500/25 group-hover:scale-105 transition-transform duration-200">
                <TrendingUp className="w-4 h-4 sm:w-5 sm:h-5 stroke-[2.5]" />
              </div>
              <div className="flex items-center gap-1.5">
                <span className="font-extrabold text-base sm:text-lg tracking-tight text-fg group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors">
                  PSXpert
                </span>
                <span className="px-1.5 py-0.2 rounded text-[10px] font-bold uppercase tracking-wider bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20">
                  AI
                </span>
              </div>
            </Link>

            {/* Quick Search Bar next to Logo (visible on xl+; collapses to search icon button on smaller/zoomed screens) */}
            <div className="hidden xl:block w-40 2xl:w-56 flex-shrink">
              <button
                type="button"
                onClick={() => setIsSearchOpen(true)}
                className="w-full flex items-center justify-between px-3 py-1.5 rounded-xl border border-border bg-bg-elevated/70 hover:bg-bg-elevated hover:border-brand-500/50 text-xs text-fg-subtle transition-all duration-150 whitespace-nowrap min-w-0"
              >
                <div className="flex items-center gap-2 min-w-0 flex-1 overflow-hidden">
                  <Search className="w-3.5 h-3.5 text-brand-600 dark:text-brand-400 flex-shrink-0" />
                  <span className="truncate whitespace-nowrap text-left block text-[11px]">Search PSX...</span>
                </div>
                <kbd className="inline-flex items-center px-1.5 py-0.2 rounded bg-bg-card border border-border text-[9px] font-mono text-fg-muted flex-shrink-0 ml-1">
                  ⌘K
                </kbd>
              </button>
            </div>
          </div>

          {/* 2. Middle: Navigation Links (Desktop Adaptive) */}
          {/* On 2xl/xl screens: Show all links. On lg screens: Show primary links + "More ▾" dropdown */}
          <nav className="hidden lg:flex items-center gap-1 xl:gap-1.5 flex-shrink">
            {primaryLinks.map(link => {
              const Icon = link.icon;
              return (
                <NavLink
                  key={link.path}
                  to={link.path}
                  className={({ isActive }) =>
                    `px-2.5 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 whitespace-nowrap transition-all duration-150 ${
                      isActive
                        ? 'text-brand-600 dark:text-brand-400 bg-brand-500/10 font-bold'
                        : 'text-fg-muted hover:text-fg hover:bg-bg-elevated'
                    }`
                  }
                >
                  <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                  <span>{link.name}</span>
                </NavLink>
              );
            })}

            {/* Secondary links: inline on 2xl, or dropdown on lg/xl */}
            <div className="hidden 2xl:flex items-center gap-1">
              {secondaryLinks.map(link => {
                const Icon = link.icon;
                return (
                  <NavLink
                    key={link.path}
                    to={link.path}
                    className={({ isActive }) =>
                      `px-2.5 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1.5 whitespace-nowrap transition-all duration-150 ${
                        isActive
                          ? 'text-brand-600 dark:text-brand-400 bg-brand-500/10 font-bold'
                          : 'text-fg-muted hover:text-fg hover:bg-bg-elevated'
                      }`
                    }
                  >
                    <Icon className="w-3.5 h-3.5 flex-shrink-0" />
                    <span>{link.name}</span>
                    {link.isNew && (
                      <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse flex-shrink-0" />
                    )}
                  </NavLink>
                );
              })}
            </div>

            {/* "More ▾" dropdown button for lg & xl viewports */}
            <div ref={moreMenuRef} className="relative 2xl:hidden">
              <button
                type="button"
                onClick={() => setIsMoreMenuOpen(!isMoreMenuOpen)}
                className={`px-2.5 py-1.5 rounded-xl text-xs font-semibold flex items-center gap-1 whitespace-nowrap transition-all duration-150 ${
                  isSecondaryActive || isMoreMenuOpen
                    ? 'text-brand-600 dark:text-brand-400 bg-brand-500/10 font-bold'
                    : 'text-fg-muted hover:text-fg hover:bg-bg-elevated'
                }`}
              >
                <span>More</span>
                <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-150 ${isMoreMenuOpen ? 'rotate-180' : ''}`} />
                {secondaryLinks.some(l => l.isNew) && (
                  <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse flex-shrink-0 ml-0.5" />
                )}
              </button>

              {/* Floating More Dropdown Menu */}
              {isMoreMenuOpen && (
                <div className="absolute left-0 mt-2 w-48 rounded-2xl bg-bg-card border border-border shadow-xl p-1.5 z-50 animate-in fade-in zoom-in-95 duration-150 space-y-0.5">
                  {secondaryLinks.map(link => {
                    const Icon = link.icon;
                    return (
                      <NavLink
                        key={link.path}
                        to={link.path}
                        onClick={() => setIsMoreMenuOpen(false)}
                        className={({ isActive }) =>
                          `flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition-colors ${
                            isActive
                              ? 'text-brand-600 dark:text-brand-400 bg-brand-500/10 font-bold'
                              : 'text-fg-muted hover:text-fg hover:bg-bg-elevated'
                          }`
                        }
                      >
                        <div className="flex items-center gap-2">
                          <Icon className="w-4 h-4 flex-shrink-0" />
                          <span>{link.name}</span>
                        </div>
                        {link.isNew && (
                          <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-brand-500/10 text-brand-600">
                            New
                          </span>
                        )}
                      </NavLink>
                    );
                  })}
                </div>
              )}
            </div>
          </nav>

          {/* 3. Right: Quick Actions Group (ALWAYS intact, flex-shrink-0, ml-auto) */}
          <div className="flex items-center gap-1 sm:gap-2 flex-shrink-0 ml-auto">
            {/* Search Icon Trigger (always visible below xl, or on mobile) */}
            <button
              onClick={() => setIsSearchOpen(true)}
              className="xl:hidden p-2 rounded-xl border border-border text-fg-muted hover:text-fg bg-bg-card hover:bg-bg-elevated transition-colors flex-shrink-0"
              aria-label="Search"
              title="Search PSX (Ctrl+K)"
            >
              <Search className="w-4 h-4 text-brand-600 dark:text-brand-400" />
            </button>

            {/* Theme Toggle */}
            <div className="flex-shrink-0">
              <ThemeToggle />
            </div>

            {/* Settings Link */}
            <Link
              to="/settings"
              className="p-2 rounded-xl border border-border text-fg-muted hover:text-fg hover:bg-bg-elevated bg-bg-card transition-colors hidden sm:inline-flex flex-shrink-0"
              title="Settings"
            >
              <Settings className="w-4 h-4" />
            </Link>

            {/* Sign In / Auth Button (Guaranteed 100% visible at all screen sizes and zooms) */}
            <button
              type="button"
              onClick={() => navigate('/portfolio')}
              className="inline-flex items-center justify-center gap-1.5 px-3 sm:px-3.5 py-1.5 sm:py-2 rounded-xl text-xs font-semibold text-white bg-brand-500 hover:bg-brand-600 shadow-sm shadow-brand-500/25 transition-colors whitespace-nowrap flex-shrink-0"
            >
              <span>Sign In</span>
            </button>

            {/* Mobile / Tablet Hamburger Toggle */}
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="lg:hidden p-2 rounded-xl border border-border text-fg-muted hover:text-fg bg-bg-card hover:bg-bg-elevated transition-colors flex-shrink-0"
              aria-label="Toggle Navigation Menu"
            >
              {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5 text-fg" />}
            </button>
          </div>
        </div>

        {/* Mobile Navigation Drawer */}
        {isMobileMenuOpen && (
          <div className="lg:hidden border-t border-border bg-bg-card px-4 pt-3 pb-6 space-y-1 shadow-lg animate-in slide-in-from-top-2 duration-150">
            <div className="mb-3">
              <button
                type="button"
                onClick={() => {
                  setIsMobileMenuOpen(false);
                  setIsSearchOpen(true);
                }}
                className="w-full flex items-center justify-between px-3 py-2.5 rounded-xl border border-border bg-bg-elevated text-xs text-fg-subtle whitespace-nowrap min-w-0"
              >
                <div className="flex items-center gap-2 min-w-0 flex-1 overflow-hidden">
                  <Search className="w-4 h-4 text-brand-600 flex-shrink-0" />
                  <span className="truncate whitespace-nowrap text-left block">Search PSX stocks, sectors...</span>
                </div>
                <kbd className="px-1.5 py-0.5 rounded bg-bg-card border border-border text-[10px] font-mono flex-shrink-0 ml-1">
                  Ctrl+K
                </kbd>
              </button>
            </div>

            {allNavLinks.map(link => {
              const Icon = link.icon;
              return (
                <NavLink
                  key={link.path}
                  to={link.path}
                  className={({ isActive }) =>
                    `flex items-center justify-between px-3 py-2.5 rounded-xl text-sm font-semibold transition-colors ${
                      isActive
                        ? 'text-brand-600 dark:text-brand-400 bg-brand-500/10 font-bold'
                        : 'text-fg-muted hover:text-fg hover:bg-bg-elevated'
                    }`
                  }
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className="w-4 h-4" />
                    <span>{link.name}</span>
                  </div>
                  {link.isNew && (
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-brand-500/10 text-brand-600">
                      New
                    </span>
                  )}
                </NavLink>
              );
            })}

            <div className="pt-3 border-t border-border flex items-center justify-between">
              <Link
                to="/settings"
                className="flex items-center gap-2 px-3 py-2 text-sm text-fg-muted"
              >
                <Settings className="w-4 h-4" />
                <span>Settings</span>
              </Link>
              <button
                type="button"
                onClick={() => navigate('/portfolio')}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-white bg-brand-500 hover:bg-brand-600"
              >
                Sign In
              </button>
            </div>
          </div>
        )}
      </header>

      {/* Global Search Dialog Modal */}
      <GlobalSearchModal
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
      />
    </>
  );
};
