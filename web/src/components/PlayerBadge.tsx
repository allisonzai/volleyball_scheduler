interface Props {
  displayName: string;
  signupNumber?: number | null;
  highlight?: boolean;
}

export default function PlayerBadge({ displayName, signupNumber, highlight }: Props) {
  return (
    <div
      className={`flex items-center gap-2 px-3 py-2 rounded-lg border w-full ${
        highlight
          ? "bg-yellow-50 border-yellow-400 font-semibold"
          : "bg-white border-gray-200"
      }`}
    >
      {signupNumber !== null && signupNumber !== undefined && (
        <span className="text-xs text-gray-400 w-6 text-right font-mono">
          #{signupNumber}
        </span>
      )}
      <span className="text-sm text-gray-800 truncate">{displayName}</span>
    </div>
  );
}
