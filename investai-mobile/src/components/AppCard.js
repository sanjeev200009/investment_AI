// src/components/AppCard.js — v2 white glass card. Kept for older call sites;
// new code uses Card from ./ui.
import React from 'react';
import { Card } from './ui';

const AppCard = ({ children, style, ...props }) => (
    <Card style={style} {...props}>{children}</Card>
);

export default AppCard;
