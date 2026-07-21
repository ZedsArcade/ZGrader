"use client";

import { useState, type ReactNode } from "react";
import { Drawer } from "@heroui/react";
import { useTranslations } from "@/lib/i18n/context";

export default function NavDrawer({ children }: { children: (close: () => void) => ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const t = useTranslations();

  return (
    <Drawer isOpen={isOpen} onOpenChange={setIsOpen}>
      <Drawer.Trigger
        aria-label={t.nav.openMenu}
        className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-foreground hover:bg-surface-hover md:hidden"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" aria-hidden="true">
          <path d="M2.5 5h15M2.5 10h15M2.5 15h15" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </Drawer.Trigger>
      <Drawer.Backdrop>
        <Drawer.Content placement="right" className="w-72 max-w-[85vw]">
          <Drawer.Dialog>
            <Drawer.Header className="flex items-center justify-between">
              <Drawer.Heading className="text-base font-semibold">{t.nav.menu}</Drawer.Heading>
              <Drawer.CloseTrigger
                aria-label={t.nav.closeMenu}
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-muted hover:bg-surface-hover"
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
                  <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </Drawer.CloseTrigger>
            </Drawer.Header>
            <Drawer.Body className="flex flex-col gap-1 py-2">{children(() => setIsOpen(false))}</Drawer.Body>
          </Drawer.Dialog>
        </Drawer.Content>
      </Drawer.Backdrop>
    </Drawer>
  );
}
