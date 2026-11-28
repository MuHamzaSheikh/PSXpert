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
  User,
  Sparkles,
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

  useEffect(() => {
    setIsMobileMenuOpen(false);
    setIsMoreMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (moreMenuRef.current && !moreMenuRef.current.contains(e.target as Node)) {
        setIsMoreMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

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
    { name: 'Settings', path: '/settings', icon: Settings },
  ];

  const allNavLinks = [...primaryLinks, ...secondaryLinks];

  const isSecondaryActive = secondaryLinks.some(link => location.pathname.startsWith(link.path));

  return (
    <>
      <header className="sticky top-0 z-40 w-full bg-[#F4EFE6]/80 dark:bg-[#141718]/80 backdrop-blur-xl border-b border-[#DDD5C9]/70 dark:border-[#DDD5C9]/15 shadow-sm">
        {/* Upper Top Status Strip */}
        <MarketStatusBar />

        {/* Floating Main Glass Navbar */}
        <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-3 w-full">
          
          {/* 1. Left: Brand Logo & Interactive Search Bar */}
          <div className="flex items-center gap-3 sm:gap-4 flex-shrink-0">
            <Link to="/" className="flex items-center gap-2 group flex-shrink-0">
              <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-gradient-to-br from-[#2F7D68] to-[#1F5C4C] flex items-center justify-center text-white shadow-md shadow-[#2F7D68]/20 group-hover:scale-105 transition-transform duration-200">
                <TrendingUp className="w-4 h-4 sm:w-5 sm:h-5 stroke-[2.5]" />
              </div>
              <div className="flex items-center gap-1.5">
                <span className="font-extrabold text-base sm:text-xl tracking-tight text-[#252A2B] dark:text-[#F4EFE6]">
                  PSXpert
                </span>
                <span className="bg-[#2F7D68]/15 text-[#2F7D68] dark:text-[#3DA88D] text-[10px] font-bold px-1.5 py-0.5 rounded-full border border-[#2F7D68]/25">
                  +AI
                </span>
              </div>
            </Link>

            {/* Quick Search Trigger Pill */}
            <button
              onClick={() => setIsSearchOpen(true)}
              className="hidden md:flex items-center gap-2 bg-[#FFFCF6]/85 dark:bg-[#1C2022]/85 hover:bg-[#FFFCF6] text-[#77736C] hover:text-[#252A2B] dark:text-[#9E988E] dark:hover:text-[#F4EFE6] px-3.5 py-1.5 rounded-full border border-[#DDD5C9]/80 dark:border-[#DDD5C9]/20 shadow-sm transition-all duration-150 text-xs w-44 lg:w-56"
            >
              <Search className="w-3.5 h-3.5 text-[#77736C]" />
              <span className="flex-1 text-left font-medium">Search PSX...</span>
              <kbd className="text-[10px] bg-[#E7E0D5]/60 dark:bg-[#252A2C] px-1.5 py-0.5 rounded font-mono border border-[#DDD5C9]/60">
                ⌘K
              </kbd>
            </button>
          </div>

          {/* 2. Center: Glass Navigation Pills */}
          <nav className="hidden lg:flex items-center gap-1.5 bg-[#FFFCF6]/65 dark:bg-[#1C2022]/65 backdrop-blur-md px-2 py-1 rounded-full border border-[#DDD5C9]/70 dark:border-[#DDD5C9]/20 shadow-sm">
            {primaryLinks.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-full text-xs font-semibold transition-all duration-200 ${
                    isActive
                      ? 'bg-gradient-to-r from-[#694E7A] to-[#543B63] text-white shadow-md shadow-[#694E7A]/25'
                      : 'text-[#77736C] dark:text-[#9E988E] hover:text-[#252A2B] dark:hover:text-[#F4EFE6] hover:bg-[#E7E0D5]/50 dark:hover:bg-[#252A2C]/60'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{item.name}</span>
                </NavLink>
              );
            })}

            {/* "More" Dropdown Menu */}
            <div className="relative" ref={moreMenuRef}>
              <button
                onClick={() => setIsMoreMenuOpen(!isMoreMenuOpen)}
                className={`flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-semibold transition-all duration-200 ${
                  isSecondaryActive
                    ? 'bg-gradient-to-r from-[#694E7A] to-[#543B63] text-white shadow-md shadow-[#694E7A]/25'
                    : 'text-[#77736C] dark:text-[#9E988E] hover:text-[#252A2B] dark:hover:text-[#F4EFE6] hover:bg-[#E7E0D5]/50 dark:hover:bg-[#252A2C]/60'
                }`}
              >
                <span>More</span>
                <ChevronDown className={`w-3.5 h-3.5 transition-transform duration-200 ${isMoreMenuOpen ? 'rotate-180' : ''}`} />
              </button>

              {isMoreMenuOpen && (
                <div className="absolute top-full right-0 mt-2 w-52 bg-[#FFFCF6]/95 dark:bg-[#1C2022]/95 backdrop-blur-xl rounded-2xl border border-[#DDD5C9] dark:border-[#DDD5C9]/20 shadow-xl p-1.5 z-50 animate-in fade-in zoom-in-95 duration-150">
                  {secondaryLinks.map((sub) => {
                    const SubIcon = sub.icon;
                    const isSubActive = location.pathname.startsWith(sub.path);
                    return (
                      <NavLink
                        key={sub.path}
                        to={sub.path}
                        onClick={() => setIsMoreMenuOpen(false)}
                        className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-colors ${
                          isSubActive
                            ? 'bg-[#694E7A]/15 text-[#694E7A] dark:text-[#A888BF] font-semibold'
                            : 'text-[#252A2B] dark:text-[#F4EFE6] hover:bg-[#E7E0D5]/60 dark:hover:bg-[#252A2C]'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <SubIcon className="w-4 h-4 text-[#77736C]" />
                          <span>{sub.name}</span>
                        </div>
                        {sub.isNew && (
                          <span className="bg-[#2F7D68]/15 text-[#2F7D68] text-[9px] font-bold px-1.5 py-0.5 rounded-full">
                            NEW
                          </span>
                        )}
                      </NavLink>
                    );
                  })}
                </div>
              )}
            </div>
          </nav>

          {/* 3. Right: Theme Toggle, Settings & User Pill */}
          <div className="flex items-center gap-2">
            {/* Search Button for Mobile */}
            <button
              onClick={() => setIsSearchOpen(true)}
              className="md:hidden p-2 rounded-full bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 border border-[#DDD5C9]/70 text-[#77736C]"
              aria-label="Search"
            >
              <Search className="w-4 h-4" />
            </button>

            {/* Circular Theme Toggle Button */}
            <ThemeToggle />

            {/* Settings Button */}
            <button
              onClick={() => navigate('/settings')}
              className="p-2 rounded-full bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 hover:bg-[#FFFCF6] border border-[#DDD5C9]/70 dark:border-[#DDD5C9]/20 text-[#77736C] hover:text-[#252A2B] transition-colors shadow-sm"
              title="Settings"
            >
              <Settings className="w-4 h-4" />
            </button>

            {/* Deep Jade Sign In Button */}
            <button
              onClick={() => {}}
              className="flex items-center gap-1.5 bg-gradient-to-r from-[#2F7D68] to-[#236353] hover:from-[#236353] hover:to-[#1a4d40] text-white text-xs font-semibold px-3.5 py-1.5 rounded-full shadow-md shadow-[#2F7D68]/20 transition-all cursor-pointer select-none leading-none"
              title="Sign In to PSXpert"
            >
              <User className="w-3.5 h-3.5 flex-shrink-0" />
              <span className="hidden sm:inline font-semibold tracking-normal antialiased">Sign In</span>
            </button>

            {/* Mobile Drawer Trigger */}
            <button
              onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
              className="lg:hidden p-2 rounded-xl bg-[#FFFCF6]/80 dark:bg-[#1C2022]/80 border border-[#DDD5C9]/70 text-[#252A2B] dark:text-[#F4EFE6]"
              aria-label="Toggle Navigation Menu"
            >
              {isMobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>

        {/* Mobile Slide-down Navigation Menu */}
        {isMobileMenuOpen && (
          <div className="lg:hidden border-t border-[#DDD5C9]/80 dark:border-[#DDD5C9]/20 bg-[#FFFCF6]/95 dark:bg-[#1C2022]/95 backdrop-blur-xl px-4 py-3 space-y-1">
            {allNavLinks.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={`flex items-center justify-between px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-gradient-to-r from-[#694E7A] to-[#543B63] text-white font-semibold shadow-sm'
                      : 'text-[#252A2B] dark:text-[#F4EFE6] hover:bg-[#E7E0D5]/50'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className="w-4 h-4" />
                    <span>{item.name}</span>
                  </div>
                  {item.isNew && (
                    <span className="bg-[#2F7D68]/15 text-[#2F7D68] text-[10px] font-bold px-1.5 py-0.5 rounded-full">
                      AI
                    </span>
                  )}
                </NavLink>
              );
            })}
          </div>
        )}
      </header>

      {/* Global Search Modal */}
      <GlobalSearchModal
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
      />
    </>
  );
};
