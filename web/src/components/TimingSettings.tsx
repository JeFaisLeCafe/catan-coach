export default function TimingSettings({
  presentationDelay,
  onPresentationDelay,
}: {
  presentationDelay: number;
  onPresentationDelay: (milliseconds: number) => void;
}) {
  return (
    <div className="timing-settings">
      <label className="presentation-delay">
        Presentation Delay
        <input
          type="number"
          min={0}
          max={5000}
          aria-label="Presentation Delay"
          value={presentationDelay}
          onChange={(event) => onPresentationDelay(Number(event.target.value))}
        />
        <span>ms</span>
      </label>
      <p className="search-budget-hint">
        Visual pause before a bot Action appears. It does not change the Action.
      </p>
    </div>
  );
}
