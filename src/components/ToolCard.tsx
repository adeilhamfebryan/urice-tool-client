import type { LucideIcon } from "lucide-react";

interface ToolCardProps {
  title: string;
  description: string;
  status: string;
  icon: LucideIcon;
  onClick?: () => void;
}

export function ToolCard({ title, description, status, icon: Icon, onClick }: ToolCardProps) {
  return (
    <article className={`tool-card ${onClick ? "clickable" : ""}`} role={onClick ? "button" : undefined} tabIndex={onClick ? 0 : undefined} onClick={onClick} onKeyDown={(event) => {
      if (onClick && (event.key === "Enter" || event.key === " ")) {
        event.preventDefault();
        onClick();
      }
    }}>
      <div className="tool-icon"><Icon size={22} /></div>
      <h3>{title}</h3>
      <p>{description}</p>
      <span>{status}</span>
    </article>
  );
}
