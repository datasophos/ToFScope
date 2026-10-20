export function UnsavedChanges({
  name,
  blocked,
  onSave,
  onDiscard,
  onCancel,
}: {
  name: string;
  blocked: string;
  onSave: () => void;
  onDiscard: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="scrim">
      <section className="dialog" role="dialog" aria-label="Unsaved changes">
        <h2>Save changes to {name}?</h2>
        <p>Your analysis has changes that are not in a saved HDF5 copy.</p>
        {blocked && <p>{blocked}</p>}
        <div className="row">
          <button disabled={!!blocked} onClick={onSave}>
            Save as…
          </button>
          <button onClick={onDiscard}>Discard</button>
          <button onClick={onCancel}>Cancel</button>
        </div>
      </section>
    </div>
  );
}
