import { Skeleton as HeroSkeleton, type SkeletonProps } from "@heroui/react";

export default function Skeleton({ animationType = "shimmer", ...props }: SkeletonProps) {
  return <HeroSkeleton animationType={animationType} {...props} />;
}
