interface Props {
  hawkishHits: Record<string, number>;
  dovishHits: Record<string, number>;
}

function cleanPhrase(pattern: string): string {
  // lexicon.py compiles phrases as \bphrase\ with\ spaces\b -- undo that for display
  return pattern.replace(/\\b/g, "").replace(/\\ /g, " ").replace(/\\/g, "");
}

export default function LexiconHits({ hawkishHits, dovishHits }: Props) {
  const hawkishEntries = Object.entries(hawkishHits);
  const dovishEntries = Object.entries(dovishHits);

  if (hawkishEntries.length === 0 && dovishEntries.length === 0) {
    return <p className="muted">No lexicon phrases matched.</p>;
  }

  return (
    <div className="lexicon-hits">
      {hawkishEntries.length > 0 && (
        <div>
          <h4 className="label-hawkish">Hawkish phrases</h4>
          <ul>
            {hawkishEntries.map(([pattern, count]) => (
              <li key={pattern}>
                "{cleanPhrase(pattern)}" &times; {count}
              </li>
            ))}
          </ul>
        </div>
      )}
      {dovishEntries.length > 0 && (
        <div>
          <h4 className="label-dovish">Dovish phrases</h4>
          <ul>
            {dovishEntries.map(([pattern, count]) => (
              <li key={pattern}>
                "{cleanPhrase(pattern)}" &times; {count}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
