/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Core navy palette — primary backgrounds
        navy: {
          950: '#060d1f',
          900: '#0a1628',
          850: '#0d1e35',
          800: '#112240',
          750: '#152a4e',
          700: '#1a3360',
          600: '#1e3a6e',
        },
        // Slate — secondary surfaces
        slate: {
          850: '#0f172a',
        },
        // Accent — primary action / highlight
        accent: {
          500: '#3b82f6',
          400: '#60a5fa',
          300: '#93c5fd',
        },
        // Cyan — secondary accent for forecasts
        cyan: {
          500: '#06b6d4',
          400: '#22d3ee',
          300: '#67e8f9',
        },
        // Emerald — actual generation
        emerald: {
          500: '#10b981',
          400: '#34d399',
          300: '#6ee7b7',
        },
        // Amber — warnings / bias
        amber: {
          500: '#f59e0b',
          400: '#fbbf24',
        },
        // Rose — errors / overforecast
        rose: {
          500: '#f43f5e',
          400: '#fb7185',
        },
        // Border / divider colours
        border: {
          subtle: 'rgba(255,255,255,0.06)',
          DEFAULT: 'rgba(255,255,255,0.10)',
          strong: 'rgba(255,255,255,0.18)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.65rem', { lineHeight: '1rem' }],
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)',
        'card-hover': '0 4px 12px rgba(0,0,0,0.5), 0 2px 4px rgba(0,0,0,0.4)',
        glow: '0 0 20px rgba(59,130,246,0.15)',
      },
      backgroundImage: {
        'grid-subtle': `linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
                        linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px)`,
      },
      backgroundSize: {
        grid: '40px 40px',
      },
      animation: {
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-in': 'slideIn 0.25s ease-out',
        pulse: 'pulse 2s cubic-bezier(0.4,0,0.6,1) infinite',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0', transform: 'translateY(4px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        slideIn: {
          from: { opacity: '0', transform: 'translateX(-8px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
      },
    },
  },
  plugins: [],
}
