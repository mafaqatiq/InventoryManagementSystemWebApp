import React from "react";
import { Box, Typography } from "@mui/material";
import Image from "next/image";

const CustomAppTitle = () => (
  <Box sx={{ display: "flex", alignItems: "center", gap: 1,marginLeft: 4 }}>
    <Image src="/logo.png" alt="My Logo" width={30} height={30} />
    <Typography variant="h6" sx={{ color: "white", fontWeight: "bold" }}>
      My Dashboard
    </Typography>
  </Box>
);

export default CustomAppTitle;
