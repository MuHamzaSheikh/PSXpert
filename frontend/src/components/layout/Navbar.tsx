import React, { useState, useEffect } from 'react';
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
  Sparkles,
} from 'lucide-react';
import { ThemeToggle } from '@/components/common/ThemeToggle';
import { MarketStatusBar } from './MarketStatusBar';
import { GlobalSearchModal } from './GlobalSearchModal';

export const Navbar: React.FC = () => {
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  // Close mobile drawer on route change
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

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

  const navLinks = [
    { name: 'Dashboard', path: '/', icon: TrendingUp },
    { name: 'AI Screener', path: '/screener', icon: SlidersHorizontal },
    { name: 'Analysis', path: '/analysis', icon: LineChart },
    { name: 'Portfolio', path: '/portfolio', icon: Briefcase },
    { name: 'AI Assistant', path: '/assistant', icon: Bot, isNew: true },
    { name: 'Research', path: '/insights', icon: FileText },
    { name: 'Watchlist', path: '/watchlist', icon: Star },
  ];

  return (
    <>
      <header className="sticky top-0 z-40 w-full bg-bg-card/95 backdrop-blur-md border-b border-border shadow-subtle">
        {/* Upper Top Status Strip */}
        <MarketStatusBar />

        {/* Main Nav Header */}
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4">
          {/* 1. Left: Brand Logo & Wordmark */}
          <Link to="/" className="flex items-center gap-2.5 flex-shrink-0 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center text-white shadow-md shadow-brand-500/25 group-hover:scale-105 transition-transform duration-200">
              <TrendingUp className="w-5 h-5 stroke-[2.5]" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="font-extrabold text-xl tracking-tight text-fg group-hover:text-brand-600 dark:group-hover:text-brand-400 transition-colors">
                  PSXpert
                </span>
                <span className="px-1.5 py-0.2 rounded text-[10px] font-bold uppercase tracking-wider bg-brand-500/10 text-brand-600 dark:text-brand-400 border border-brand-500/20">
                  AI
                </span>
              </div>
              <span className="text-[10px] font-medium text-fg-subtle tracking-wide hidden sm:inline">
                Pakistan Stock Exchange Intelligence
              </span>
            </div>
          </Link>

          {/* 2. Middle: Navigation Links (Desktop) */}
          <nav className="hidden lg:flex items-center gap-1 xl:gap-2">
            {navLinks.map(link => {
              const Icon = link.icon;
              return (
                <NavLink
                  key={link.path}
                  to={link.path}
                  className={({ isActive }) =>
                    `relative px-3 py-2 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition-all duration-150 ${
                      isActive
                        ? 'text-brand-600 dark:text-brand-400 bg-brand-500/10 font-bold'
                        : 'text-fg-muted hover:text-fg hover:bg-bg-elevated'
                    }`
                  }
                >
                  <Icon className="w-4 h-4" />
                  <span>{link.name}</span>
                  {link.isNew && (
                    <span className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-pulse" />
                  )}
                </NavLink>
              );
            })}
          </nav>

          {/* 3. Center/Right: Global Search Omnibar */}
          <div className="flex-1 max-w-xs xl:max-w-sm hidden md:block">
            <button
              type="button"
              onClick={() => setIsSearchOpen(true)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-xl border border-border bg-bg-elevated/70 hover:bg-bg-elevated hover:border-brand-500/50 text-xs text-fg-subtle transition-all duration-150"
            >
              <div className="flex items-center gap-2">
                <Search className="w-4 h-4 text-brand-600 dark:text-brand-400" />
                <span>Search stocks, sectors...</span>
              </div>
              <kbd className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-bg-card border border-border text-[10px] font-mono text-fg-muted">
                ⌘K
              </kbd>
            </button>
          </div>

          {/* 4. Right: Quick Actions */}
          <div className="flex items-center gap-2">
            {/* Mobile Search Icon */}
            <button
              onClick={() => setIsSearchOpen(true)}
              className="md:hidden p-2 rounded-lg border border-border text-fg-muted hover:text-fg bg-bg-card"
              aria-label="Search"
            >
              <Search className="w-4 h-4" />
            </button>

            {/* Theme Toggle */}
            <ThemeToggle />

            {/* Settings Link */}
            <Link
              to="/settings"
              className="p-2 rounded-lg border border-border text-fg-muted hover:text-fg hover:bg-bg-elevated bg-bg-card transition-colors hidden sm:inline-flex"
              title="Settings"
            >
              <Settings className="w-4 h-4" />
            </Link>

            {/* Login / Auth Button */}
            <button
              type="button"
              onClick={() => navigate('/portfolio')}
              className="hidden sm:inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold text-white bg-brand-500 hover:bg-brand-600 shadow-sm shadow-brand-500/25 transition-colors"
            >
              <span>Sign In</span>
            </button>

            {/* Mobile Hamburger Toggle */}
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="lg:hidden p-2 rounded-lg border border-border text-fg-muted hover:text-fg bg-bg-card"
              aria-label="Toggle Navigation Menu"
            >
              {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
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
                className="w-full flex items-center justify-between px-3 py-2.5 rounded-xl border border-border bg-bg-elevated text-xs text-fg-subtle"
              >
                <div className="flex items-center gap-2">
                  <Search className="w-4 h-4 text-brand-600" />
                  <span>Search PSX stocks, sectors...</span>
                </div>
                <kbd className="px-1.5 py-0.5 rounded bg-bg-card border border-border text-[10px] font-mono">
                  Ctrl+K
                </kbd>
              </button>
            </div>

            {navLinks.map(link => {
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
