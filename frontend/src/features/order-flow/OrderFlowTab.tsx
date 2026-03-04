import React from 'react';
import type { OrderFlowData } from '../../types/api';
import OrderFlowHeader from './OrderFlowHeader';
import VolumeProfileChart from './VolumeProfileChart';
import VWAPChart from './VWAPChart';
import OrderBookPanel from './OrderBookPanel';

interface OrderFlowTabProps {
    data: OrderFlowData | null | undefined;
    futuresLtp?: number;
}

const OrderFlowTab: React.FC<OrderFlowTabProps> = ({ data, futuresLtp }) => {
    return (
        <div>
            <OrderFlowHeader data={data} futuresLtp={futuresLtp} />
            <div className="grid gap-3 lg:grid-cols-3 p-2">
                <VolumeProfileChart
                    profile={data?.volume_profile ?? []}
                    poc={data?.poc ?? 0}
                    valueAreaHigh={data?.value_area_high ?? 0}
                    valueAreaLow={data?.value_area_low ?? 0}
                />
                <VWAPChart data={data} futuresLtp={futuresLtp} />
                <OrderBookPanel data={data} />
            </div>
        </div>
    );
};

export default React.memo(OrderFlowTab);
