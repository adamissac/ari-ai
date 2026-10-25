/** Decorative floating geometry behind focused flows. Purely visual; hidden from assistive tech. */
export function BackdropShapes() {
  return (
    <div className="backdrop-shapes" aria-hidden="true">
      <span className="shape shape-ring s1" />
      <span className="shape shape-orb s2" />
      <span className="shape shape-square s3" />
      <span className="shape shape-ring s4" />
      <span className="shape shape-tri s5" />
      <span className="shape shape-orb s6" />
      <span className="shape shape-square s7" />
    </div>
  );
}
