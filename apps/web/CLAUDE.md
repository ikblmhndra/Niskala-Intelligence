@AGENTS.md

# shadcn/ui di sini pakai Base UI, BUKAN Radix

`components.json`/`ui/*.tsx` yang di-generate CLI pakai `@base-ui/react`
(shadcn migrasi dari Radix). Komposisi trigger/close pakai prop
**`render={<Element />}`**, BUKAN `asChild` + children -- `asChild`
DIAM-DIAM gak dikenali (bukan error), Trigger tetep render `<button>`
default-nya SENDIRI di sekeliling child `<Button>` manapun yang dikasih
lewat children, hasilnya `<button>` nested (React hydration error,
KETEMU LIVE pas testing Grup A `ChangelogDialog`/`UserMenu`). Contoh
bener: lihat `DialogPrimitive.Close` di `ui/dialog.tsx`.

`DropdownMenuLabel` (`MenuPrimitive.GroupLabel`) juga WAJIB dibungkus
`<DropdownMenuGroup>` -- beda dari Radix yang boleh berdiri sendiri,
Base UI lempar runtime error ("MenuGroupContext is missing") kalau
enggak. KETEMU LIVE juga (`UserMenu`).

`SelectItem` children WAJIB satu string tunggal, BUKAN beberapa
ekspresi/teks JSX (`{a}{b}` atau `{a} literal`) -- Base UI Select
extract label/value item itu buat typeahead (`useTypeahead`) dan
keyboard-select matching (`SelectRoot.js` manggil `.toLowerCase()` di
hasil extract-nya), kalau children-nya array node (bukan string
tunggal) hasil extract-nya bukan string → `Uncaught TypeError:
c.toLowerCase is not a function`, crash SELURUH Select (bukan cuma item
itu). KETEMU LIVE Grup C (`AddUserForm`'s Role select, dua children
`{r.name}{cond ? ... : ""}`) -- fix: gabung jadi satu
`{cond ? `${a} — ${b}` : a}`.
