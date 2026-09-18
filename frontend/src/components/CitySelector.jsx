import { MapPin } from "lucide-react";
import { CITIES } from "../data/cities";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

export default function CitySelector({ value, onChange }) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger
        aria-label="Elegir ciudad"
        className="h-9 w-[190px] gap-2 rounded-full border-border bg-card/85 pl-3 font-semibold shadow-lg backdrop-blur focus:ring-primary"
      >
        <MapPin className="h-4 w-4 shrink-0 text-primary" />
        <SelectValue />
      </SelectTrigger>
      <SelectContent className="max-h-72">
        {CITIES.map((c) => (
          <SelectItem key={c.name} value={c.name}>
            {c.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
