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
