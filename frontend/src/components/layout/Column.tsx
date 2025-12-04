import React from "react";

interface Props {
  children?: React.ReactNode;
  className?: string;
  width?: string;
}

const Column: React.FC<Props> = ({ children, className, width }) => {
  const style = width ? { flex: `0 0 ${width}` } : { flex: "1 1 0" };
  return (
    <div style={style} className={`column flex flex-col gap-4 ${className ?? ""}`}>
      {children}
    </div>
  );
};

export default Column;