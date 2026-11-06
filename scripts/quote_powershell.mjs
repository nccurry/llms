// PowerShell treats all of these characters as a single quote inside a '...' string:
// ' U+2018 U+2019 U+201A U+201B. Each one is doubled to stay literal.
// Keep in step with powershell_quote in manage_agent_tools.py.
const singleQuotes = /['\u2018\u2019\u201a\u201b]/g;

export function quotePowerShell(value) {
  return `'${value.replace(singleQuotes, (quote) => quote + quote)}'`;
}
