interface Props {
  content: string;
}

export function ProgressBar({ content }: Props) {
  return (
    <div className="flex items-center gap-2 text-sm text-gray-500 py-1">
      <div className="animate-spin w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full" />
      <span>{content}</span>
    </div>
  );
}
