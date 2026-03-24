import { useEffect, useState } from "react";
import { getActivity } from "../api/client";
import type { EventEntry } from "../types";

const TYPE_STYLE: Record<string, { dot: string; text: string }> = {
  game_staged:      { dot: "bg-yellow-400", text: "text-yellow-700" },
  game_begun:       { dot: "bg-green-500",  text: "text-green-700"  },
  game_force_begun: { dot: "bg-green-500",  text: "text-green-700"  },
  game_ended:       { dot: "bg-blue-400",   text: "text-blue-700"   },
  player_confirmed: { dot: "bg-green-400",  text: "text-green-700"  },
  player_declined:  { dot: "bg-orange-400", text: "text-orange-700" },
  player_deferred:  { dot: "bg-blue-300",   text: "text-blue-700"   },
  player_timed_out: { dot: "bg-red-400",    text: "text-red-700"    },
  player_filled:    { dot: "bg-purple-400", text: "text-purple-700" },
  player_left:      { dot: "bg-orange-400", text: "text-orange-700" },
  settings_updated: { dot: "bg-gray-400",   text: "text-gray-600"   },
};

const DEFAULT_STYLE = { dot: "bg-gray-300", text: "text-gray-600" };

export default function ActivityView() {
  const [events, setEvents] = useState<EventEntry[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getActivity()
      .then(setEvents)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="text-center text-gray-400 py-8">Loading…</div>;
  }

  return (
    <div className="bg-white rounded-2xl shadow p-5">
      <h2 className="text-lg font-bold text-gray-800 mb-4">Event Log</h2>
      {events.length === 0 ? (
        <p className="text-gray-400 text-sm text-center py-4">No events yet.</p>
      ) : (
        <ol className="relative border-l border-gray-200 space-y-4 ml-2">
          {events.map((e) => {
            const style = TYPE_STYLE[e.event_type] ?? DEFAULT_STYLE;
            const ts = new Date(e.created_at + "Z").toLocaleString([], {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
              hour12: false,
            });
            return (
              <li key={e.id} className="ml-4">
                <span
                  className={`absolute -left-1.5 mt-1.5 h-3 w-3 rounded-full border-2 border-white ${style.dot}`}
                />
                <p className="text-xs text-gray-400 mb-0.5">{ts}</p>
                <p className={`text-sm font-medium ${style.text}`}>
                  {e.description}
                </p>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
