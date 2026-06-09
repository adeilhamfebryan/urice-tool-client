import logoUrl from "../assets/urice_logo.ico";

export function BrandScene() {
  return (
    <div className="brand-scene" aria-hidden="true">
      <div className="logo-3d-stage">
        <div className="logo-3d-shadow" />
        <div className="logo-3d-card">
          <div className="logo-3d-rim" />
          <img src={logoUrl} alt="" />
        </div>
      </div>
    </div>
  );
}
