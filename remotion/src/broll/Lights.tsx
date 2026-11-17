import React from "react";

// Three-point rig: warm key, purple rim (matches the speaker's backdrop), soft fill.
export const Lights: React.FC<{ rim?: string }> = ({ rim = "#7A5CFF" }) => (
  <>
    <ambientLight intensity={0.55} />
    <directionalLight position={[4, 6, 6]} intensity={2.2} color="#fff4e0" />
    <directionalLight position={[-5, 2, -4]} intensity={1.6} color={rim} />
    <pointLight position={[0, -3, 4]} intensity={18} distance={14} color="#ffd9a0" />
  </>
);

export const Gold: React.FC = () => <meshStandardMaterial color="#F2C230" metalness={0.55} roughness={0.28} emissive="#5a3a00" emissiveIntensity={0.25} />;
