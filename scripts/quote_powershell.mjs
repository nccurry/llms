// PowerShell treats all of these characters as a single quote inside a '...' string,
// so each one is doubled to stay literal.
const singleQuotes = /['‘’‚‛]/g;

export function quotePowerShell(value) {
  return `'${value.replace(singleQuotes, (quote) => quote + quote)}'`;
}
