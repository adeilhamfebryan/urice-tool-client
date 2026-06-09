import type { LucideIcon } from "lucide-react";

interface ToolCardProps {
  title: string;
  description: string;
  status: string;
  icon: LucideIcon;
}

export function ToolCard({ title, description, status, icon: Icon }: ToolCardProps) {
  return (
    <article className="tool-card">
      <div className="tool-icon"><Icon size={22} /></div>
      <h3>{title}</h3>
      <p>{description}</p>
      <span>{status}</span>
    </article>
  );
}
