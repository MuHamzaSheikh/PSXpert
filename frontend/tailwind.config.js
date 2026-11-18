/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f9f9',
          100: '#d7efef',
          200: '#b2dfdf',
          300: '#7fc5c5',
          400: '#4da6a6',
          500: '#238989', // Core Investify-inspired teal
          600: '#1b6e6e',
          700: '#165757',
          800: '#134646',
          900: '#0f2929',
          950: '#071818',
        },
        bull: {
          DEFAULT: '#10b981',
          light: '#d1fae5',
          dark: '#047857',
          bg: 'rgba(16, 185, 129, 0.12)',
        },
        bear: {
          DEFAULT: '#f43f5e',
          light: '#ffe4e6',
          dark: '#be123c',
          bg: 'rgba(244, 63, 94, 0.12)',
        },
        border: 'var(--color-border)',
        bg: {
          DEFAULT: 'var(--color-bg)',
          card: 'var(--color-bg-card)',
          elevated: 'var(--color-bg-elevated)',
          subtle: 'var(--color-bg-subtle)',
        },
        fg: {
          DEFAULT: 'var(--color-fg)',
          muted: 'var(--color-fg-muted)',
          subtle: 'var(--color-fg-subtle)',
        }
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        '2xl': '16px',
        '3xl': '20px',
      },
      boxShadow: {
        'subtle': '0 1px 3px 0 rgba(0, 0, 0, 0.05), 0 1px 2px -1px rgba(0, 0, 0, 0.05)',
        'card': '0 4px 6px -1px rgba(0, 0, 0, 0.06), 0 2px 4px -2px rgba(0, 0, 0, 0.04)',
        'card-hover': '0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -4px rgba(0, 0, 0, 0.04)',
      }
    },
  },
  plugins: [],
}
