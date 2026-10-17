const WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];

/** Small counts as words ("five"), larger ones as digits. */
export function countWord(n: number): string {
  return Number.isInteger(n) && n >= 0 && n < WORDS.length ? WORDS[n]! : String(n);
}

/** "five machines", or a range when scenarios differ. Derived from the bundle, never fixed text. */
export function machineCountPhrase(scenarios: readonly { nodes: readonly unknown[] }[]): string {
  const counts = scenarios.map(s => s.nodes.length);
  if (counts.length === 0) return 'machines';
  const min = Math.min(...counts);
  const max = Math.max(...counts);
  if (min === max) return `${countWord(min)} ${min === 1 ? 'machine' : 'machines'}`;
  return `${countWord(min)} to ${countWord(max)} machines`;
}

/** "Four defenders" / "four" with correct singular. */
export function defenderCountPhrase(n: number, capitalize = false): string {
  const text = `${countWord(n)} ${n === 1 ? 'defender' : 'defenders'}`;
  return capitalize ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}
