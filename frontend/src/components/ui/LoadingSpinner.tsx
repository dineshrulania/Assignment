import { Loader2 } from 'lucide-react';

interface Props {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
  fullHeight?: boolean;
}

const sizeMap = { sm: 16, md: 24, lg: 36 };

export default function LoadingSpinner({ message, size = 'md', fullHeight = false }: Props) {
  return (
    <div className={`flex flex-col items-center justify-center gap-3 text-slate-500
                     ${fullHeight ? 'min-h-[320px]' : 'py-12'}`}>
      <Loader2 size={sizeMap[size]} className="animate-spin text-accent-500" />
      {message && <p className="text-sm">{message}</p>}
    </div>
  );
}
