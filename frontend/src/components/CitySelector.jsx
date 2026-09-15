import { CITIES } from "../data/cities";
import { IcPin, IcChevron } from "../icons.jsx";

export default function CitySelector({ value, onChange }) {
  return (
    <div className="citysel">
      <IcPin size={16} />
      <select value={value} onChange={(e) => onChange(e.target.value)} aria-label="Elegir ciudad">
        {CITIES.map((c) => (
          <option key={c.name} value={c.name}>{c.name}</option>
        ))}
      </select>
      <IcChevron size={14} />
    </div>
  );
}
