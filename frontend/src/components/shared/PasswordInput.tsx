import { useState } from "react";
import { Eye, EyeOff, Lock } from "lucide-react";

interface Props {
  value: string;
  onChange: (v: string) => void;
  label?: string;
}

export function PasswordInput({ value, onChange, label }: Props) {
  const [show, setShow] = useState(false);

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        <Lock className="w-3.5 h-3.5 inline mr-1" />
        {label ?? "Senha de proteção (opcional)"}
      </label>
      <div className="relative">
        <input
          type={show ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Deixe vazio para não proteger"
          className="w-full border border-gray-300 rounded-lg px-3 py-2 pr-10 text-sm focus:ring-2 focus:ring-[#5BA8D9] focus:border-transparent outline-none"
        />
        <button
          type="button"
          onClick={() => setShow(!show)}
          className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
        >
          {show ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
}
