import React from "react";

interface Props {
  children?: React.ReactNode;
  className?: string;
}

const DashboardLayout: React.FC<Props> = ({ children, className }) => {
  return (
    <div className={`dashboard-layout min-h-screen p-4 bg-gray-50 ${className ?? ""}`}>
      {children}
    </div>
  );
};

export default DashboardLayout;