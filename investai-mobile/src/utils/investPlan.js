// Turn "I have LKR X" into whole shares of each recommended company: the amount is
// split equally, and each share's cost includes the broker fee. An example for
// learning, not an order; the app never trades.

// CSE retail brokerage plus levies, per buy, as a share of the trade value.
export const BROKER_FEE = 0.0112;

export function splitAmount(amount, picks, fee = BROKER_FEE) {
  const priced = picks.filter(p => p.price > 0);
  if (!(amount > 0) || priced.length === 0) return null;
  // Split across as many companies as the amount can buy at least one share of,
  // cheapest first; a company too expensive for its slice gets 0 shares and its
  // slice goes to the others instead of sitting unused.
  const byPrice = [...priced].sort((a, b) => a.price - b.price);
  let k = byPrice.length;
  while (k > 0 && byPrice[k - 1].price * (1 + fee) > amount / k) k -= 1;
  const buyable = byPrice.slice(0, k);
  const each = k ? amount / k : 0;
  const rows = priced.map(p => {
    const shares = buyable.includes(p) ? Math.floor(each / (p.price * (1 + fee))) : 0;
    const cost = shares * p.price;
    return { symbol: p.symbol, shares, cost, fee: cost * fee };
  });
  const fees = rows.reduce((s, r) => s + r.fee, 0);
  const spent = rows.reduce((s, r) => s + r.cost, 0) + fees;
  return { rows, fees, spent, left: amount - spent };
}
