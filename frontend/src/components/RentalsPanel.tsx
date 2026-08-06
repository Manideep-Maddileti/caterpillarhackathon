import { useMemo, useState } from "react";
import type { Equipment, Rental, Site } from "../types";
import { createCustomer, createRental, checkoutRental, checkinRental } from "../api";
import { Button, Card, StatusBadge } from "./ui";

type Step = "availability" | "new-customer";

export default function RentalsPanel({
  equipment, rentals, sites, onChange,
}: {
  equipment: Equipment[];
  rentals: Rental[];
  sites: Site[];
  onChange: () => void;
}) {
  const [step, setStep] = useState<Step>("availability");
  const [search, setSearch] = useState("");
  const [chosenEquipment, setChosenEquipment] = useState<Equipment | null>(null);

  const [customerName, setCustomerName] = useState("");
  const [customerCompany, setCustomerCompany] = useState("");
  const [customerContact, setCustomerContact] = useState("");
  const [siteId, setSiteId] = useState<number | "">("");
  const [rentalDays, setRentalDays] = useState(7);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [qrModal, setQrModal] = useState<Rental | null>(null);

  // An equipment can look "available" on its own status field but already have
  // an un-checked-out rental pending (created, not yet scanned out) — exclude those too.
  const pendingEquipmentIds = new Set(
    rentals.filter((r) => r.status === "created" || r.status === "active").map((r) => r.equipment_id)
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return equipment;
    return equipment.filter(
      (e) =>
        e.equipment_code.toLowerCase().includes(q) ||
        e.type.toLowerCase().includes(q) ||
        (e.assigned_site?.site_code ?? "").toLowerCase().includes(q)
    );
  }, [equipment, search]);

  const startRental = (eq: Equipment) => {
    setChosenEquipment(eq);
    setSiteId(eq.assigned_site_id ?? "");
    setCustomerName("");
    setCustomerCompany("");
    setCustomerContact("");
    setRentalDays(7);
    setError("");
    setStep("new-customer");
  };

  const backToAvailability = () => {
    setChosenEquipment(null);
    setStep("availability");
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chosenEquipment || !customerName.trim()) return;
    setBusy(true);
    setError("");
    try {
      const customer = await createCustomer({
        name: customerName.trim(),
        company: customerCompany.trim() || undefined,
        contact: customerContact.trim() || undefined,
      });
      const rental = await createRental({
        equipment_id: chosenEquipment.id,
        customer_id: customer.id,
        site_id: siteId ? Number(siteId) : undefined,
        rental_days: rentalDays,
      });
      // Generating the QR IS the scan in this simulated flow — check out
      // immediately instead of requiring a separate manual click.
      const activeRental = await checkoutRental(rental.id);
      setQrModal(activeRental);
      onChange();
      backToAvailability();
    } catch {
      setError("Could not create the rental — the machine may no longer be available.");
    } finally {
      setBusy(false);
    }
  };

  const doCheckout = async (id: number) => {
    await checkoutRental(id);
    onChange();
    setQrModal(null);
  };

  const doCheckin = async (id: number) => {
    await checkinRental(id);
    onChange();
  };

  const equipmentByRental = (r: Rental) => equipment.find((e) => e.id === r.equipment_id);

  return (
    <div className="space-y-4">
      {step === "availability" && (
        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-stone-700">Step 1 — Check machine availability</h3>
            <input
              type="text"
              placeholder="Search by code, type or site…"
              className="border border-stone-300 rounded-lg px-3 py-1.5 text-sm w-64"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="overflow-x-auto max-h-[28rem] overflow-y-auto">
            <table className="min-w-full text-sm">
              <thead className="sticky top-0 bg-white">
                <tr className="text-left text-xs uppercase tracking-wide text-stone-500 border-b border-stone-200">
                  <th className="py-2 pr-4">Equipment</th>
                  <th className="py-2 pr-4">Type</th>
                  <th className="py-2 pr-4">Site</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Action</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((e) => {
                  const isAvailable = e.status === "available" && !pendingEquipmentIds.has(e.id);
                  return (
                    <tr key={e.id} className="border-b border-stone-100 hover:bg-stone-50">
                      <td className="py-2 pr-4 font-medium text-stone-900">{e.equipment_code}</td>
                      <td className="py-2 pr-4">{e.type}</td>
                      <td className="py-2 pr-4">{e.assigned_site?.site_code ?? "Unassigned"}</td>
                      <td className="py-2 pr-4"><StatusBadge status={e.status} /></td>
                      <td className="py-2 pr-4">
                        {isAvailable ? (
                          <Button onClick={() => startRental(e)}>Rent this machine →</Button>
                        ) : (
                          <span className="text-xs text-stone-400">Not available</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {step === "new-customer" && chosenEquipment && (
        <Card className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-stone-700">
              Step 2 — Create new customer for {chosenEquipment.equipment_code} ({chosenEquipment.type})
            </h3>
            <button onClick={backToAvailability} className="text-xs text-stone-900 underline decoration-brand-500 decoration-2 underline-offset-2 hover:text-brand-700">
              ← Back to availability
            </button>
          </div>
          <form onSubmit={submit} className="grid grid-cols-2 md:grid-cols-3 gap-3 items-end">
            <div>
              <label className="text-xs text-stone-500">Customer name *</label>
              <input
                required
                className="mt-1 w-full border border-stone-300 rounded-lg px-2 py-1.5 text-sm"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-stone-500">Company</label>
              <input
                className="mt-1 w-full border border-stone-300 rounded-lg px-2 py-1.5 text-sm"
                value={customerCompany}
                onChange={(e) => setCustomerCompany(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-stone-500">Contact</label>
              <input
                className="mt-1 w-full border border-stone-300 rounded-lg px-2 py-1.5 text-sm"
                value={customerContact}
                onChange={(e) => setCustomerContact(e.target.value)}
              />
            </div>
            {chosenEquipment.assigned_site_id ? (
              <div>
                <label className="text-xs text-stone-500">Site</label>
                <p className="mt-1 text-sm py-1.5">{chosenEquipment.assigned_site?.site_code} (fixed)</p>
              </div>
            ) : (
              <div>
                <label className="text-xs text-stone-500">Site</label>
                <select
                  className="mt-1 w-full border border-stone-300 rounded-lg px-2 py-1.5 text-sm"
                  value={siteId}
                  onChange={(ev) => setSiteId(ev.target.value ? Number(ev.target.value) : "")}
                >
                  <option value="">Select…</option>
                  {sites.map((s) => (
                    <option key={s.id} value={s.id}>{s.site_code}</option>
                  ))}
                </select>
              </div>
            )}
            <div>
              <label className="text-xs text-stone-500">Rental days</label>
              <input
                type="number"
                min={1}
                className="mt-1 w-full border border-stone-300 rounded-lg px-2 py-1.5 text-sm"
                value={rentalDays}
                onChange={(e) => setRentalDays(Number(e.target.value))}
              />
            </div>
            <Button type="submit" disabled={!customerName.trim() || busy}>Create customer + Generate QR</Button>
          </form>
          {error && <p className="text-xs text-red-600 mt-2">{error}</p>}
        </Card>
      )}

      <Card className="p-4">
        <h3 className="text-sm font-semibold text-stone-700 mb-3">Rental history</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-wide text-stone-500 border-b border-stone-200">
                <th className="py-2 pr-4">Equipment</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2 pr-4">Return date</th>
                <th className="py-2 pr-4">QR</th>
                <th className="py-2 pr-4">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rentals.map((r) => {
                const eq = equipmentByRental(r);
                return (
                  <tr key={r.id} className="border-b border-stone-100">
                    <td className="py-2 pr-4 font-medium">{eq?.equipment_code ?? r.equipment_id}</td>
                    <td className="py-2 pr-4"><StatusBadge status={r.status} /></td>
                    <td className="py-2 pr-4">{r.return_date ? new Date(r.return_date).toLocaleString() : "—"}</td>
                    <td className="py-2 pr-4">
                      {r.qr_code && (
                        <button onClick={() => setQrModal(r)} className="text-stone-900 text-xs underline decoration-brand-500 decoration-2 underline-offset-2 hover:text-brand-700">
                          View QR
                        </button>
                      )}
                    </td>
                    <td className="py-2 pr-4 space-x-2">
                      {r.status === "created" && (
                        <Button variant="secondary" onClick={() => doCheckout(r.id)}>Scan → Check Out</Button>
                      )}
                      {r.status === "active" && (
                        <Button variant="secondary" onClick={() => doCheckin(r.id)}>Scan → Check In</Button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>

      {qrModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={() => setQrModal(null)}>
          <Card className="p-6 text-center" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm font-semibold mb-3">
              Rental QR — {equipmentByRental(qrModal)?.equipment_code}
            </h3>
            {qrModal.qr_code && <img src={qrModal.qr_code} alt="Rental QR" className="mx-auto w-48 h-48" />}
            {qrModal.status === "active" ? (
              <p className="text-xs text-emerald-600 mt-3 font-medium">
                Checked out automatically — rental is now active. Keep this QR for the customer's records.
              </p>
            ) : (
              <div className="mt-3">
                <p className="text-xs text-stone-500 mb-2">Scan to check this rental out.</p>
                <Button onClick={() => doCheckout(qrModal.id)}>Scan → Check Out</Button>
              </div>
            )}
            <div className="flex gap-2 justify-center mt-4">
              <Button variant="secondary" onClick={() => setQrModal(null)}>Close</Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
