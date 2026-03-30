interface Props {
  value: string;
  onChange: (v: string) => void;
  maxPages?: number;
  label?: string;
}

export function PageRangeInput({ value, onChange, maxPages, label }: Props) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label ?? "Paginas"}
      </label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={`Ex: 1, 3-5, 10${maxPages ? ` (max: ${maxPages})` : ""}`}
        className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-[#5BA8D9] focus:border-transparent outline-none"
      />
      <p className="text-xs text-gray-400 mt-1">
        Separe por virgula ou use intervalos (ex: 1-5)
      </p>
    </div>
  );
}
