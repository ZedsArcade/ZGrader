import { Button as HeroButton, cn, type ButtonProps } from "@heroui/react";

export default function Button({ className, ...props }: ButtonProps) {
  return <HeroButton className={cn("btn-press btn-neon-hover", className)} {...props} />;
}
