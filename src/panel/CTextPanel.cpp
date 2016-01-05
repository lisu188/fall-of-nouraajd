//#include "CGamePanel.h"
//#include "core/CGame.h"
//
//CTextPanel::CTextPanel() {
//    this->setZValue ( 7 );
//}
//
//QRectF CTextPanel::boundingRect() const {
//    return QRectF ( 0, 0, 400, 300 );
//}
//
//void CTextPanel::paint ( QPainter *painter, const QStyleOptionGraphicsItem *, QWidget * ) {
//    QFont font = painter->font();
//    painter->fillRect ( boundingRect(), QColor ( "BLACK" ) );
//    QPen penHText ( QColor ( "WHITE" ) );
//    painter->setPen ( penHText );
//    painter->drawText ( 0, font.pointSize(), 400, 300, Qt::AlignLeft | Qt::TextWordWrap | Qt::AlignJustify, text );
//}
//
//void CTextPanel::showPanel() {
//    this->setVisible ( true );
//    this->setPos (
//        view.lock()->mapToScene ( view.lock()->width() / 2 - this->boundingRect().width() / 2,
//                                  view.lock()->height() / 2 - this->boundingRect().height() / 2 ) );
//    this->update();
//}
//
//void CTextPanel::hidePanel() {
//    this->setVisible ( false );
//}
//
//void CTextPanel::update() {
//
//}
//
//void CTextPanel::setUpPanel ( std::shared_ptr<CGameView> view ) {
//    this->view = view;
//}
//
//std::string CTextPanel::getText() const {
//    return text;
//}
//
//void CTextPanel::setText ( const std::string &value ) {
//    text = value;
//}
//
//std::string CTextPanel::getPanelName() {
//    return "CTextPanel";
//}
//
